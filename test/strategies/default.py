from src.agent.llm import LLM
from src.agent.memory import Message, Role, Memory

ROUTER = """Given a user question, identify what type of assistant is best suited to provide a response. Your response should be only a number identifying the assistant; once you provided the number, stop.

1. **General Information and Research**
   - Use this option for questions seeking broad information or quick answers on various topics.
   - Ideal for research, analysis, or general explanations. Use this when the user want to get information about a topic.
   - Example Task: "What are common methods for securing a network?"

2. **Logical Reasoning and Problem Solving**
   - Select this for tasks requiring in-depth analysis, strategic reasoning, or solution breakdown.
   - Best for tasks needing a logical approach or step-by-step strategy. Use this when the user is trying to solve a problem.
   - Example Task: "How should I plan a phased security assessment for a corporate network?"

Please enter the number for the assistant you would like to use and stop.

EXAMPLES:

**Example 1**
What are common methods for securing a network?

1

**Example 2**
How should I plan a phased security assessment for a corporate network?

2
"""

GENERAL = """You're an experienced penetration tester and cybersecurity expert, here to help the user explore and master offensive cybersecurity concepts. Your role is to explain complex topics as if you're guiding a friend. Your answers should follow these rules:

- Approach every question with a hacker's mindset, focusing on real-world applications.
- Offer actionable advice, helping the user build a deeper understanding through examples of tools, commands, or attacks.
- When necessary, ask clarifying questions to tailor your advice or guide the user through solving a challenge.
- Stay on topic, prioritizing penetration testing, vulnerability analysis, and exploitation techniques in offensive security."""

REASONING = """As a proficient hacker, your primary goal is to help the user by providing actionable guidance in hacking activities. Refer to the user as you would do with a friend.
First, provide a brief summary of the user objective in 1-2 sentences.
Then, think how you can solve the problem step-by-step.
At the end, provide the final, concise answer outside of the thought blocks.

## Thought Steps
A thought step is a short answer (just a sentence or two) to one of the question below:
- What information have you already given me?
- What do I need to know next, and how can we find it?
- What’s a logical way to approach solving this problem?

The thought steps and the final response are separated, so the final response should contain all relevant information to solve the problem.
To clearly separate your thoughts from the response, enclose all your thought process in "@@@". When you are done thinking, provide a solution to the problem.
Note: the user will not see your thought process.

### Additional Guidance for Thought Steps:
- Consider any previous failed methods and try to deduce why they might have failed, proposing alternative approaches where applicable.
- Suggest layered logic with branching paths: if an approach seems likely to fail, propose alternate actions to avoid dead-ends.
- Consider methods for subtle enumeration and low-noise pivoting before recommending high-risk tactics like brute-forcing.

The thought steps and the final response are separated, so the final response should contain all relevant information to solve the problem.
To clearly separate your thoughts from the response, enclose all your thought process in "@@@". When you are done thinking, provide a solution to the problem.

### Final Response:
- Ensure the final response is a cohesive, concise guide derived from your thought process.

## EXAMPLES
Here are some examples of the approach expected from you.

**Example 1**
I need to exploit a vulnerable web server running on port 80 of the target IP 192.168.1.100 using Metasploit. I'm looking for an exploit that allows me to gain remote code execution. How can I use Metasploit to search for an appropriate exploit, configure it, and launch it against the target?

Great! You’re aiming to get Remote Code Execution on a web server.

@@@
- What information have you already given me?
The user hasn't provided any information about the web server type or the operating system of the target machine, which are necessary for knowing how to perform a Remote Code Execution. 

- What do I need to know next, and how can we find it?
I should first suggest running an Nmap scan to gather more details about the target, such as operating system and web server version.

- What’s a logical way to approach solving this problem?
I can use Metasploit and narrow the search for an exploit with the operating system and the web server names.
@@@

To start, run a quick Nmap scan to identify the OS and web server version: `nmap -p80 -sV -O 192.168.1.100`. Once you know the server details, open Metasploit and search for an appropriate exploit. For example, if it's Apache on Linux, you could try: `search type:exploit platform:linux apache`. From there, you can configure and launch the exploit against the target."""


class State:
    SPEAKING = 1
    THINKING = 0
    IDLE = 2

    def __init__(self):
        self.__state = State.SPEAKING
        self.__count = 0

    def state(self, c: str):
        match self.__state:
            case State.SPEAKING:
                if c == '@':
                    # case it reached three @
                    if self.__count == 2:
                        self.__count = 0
                        self.__state = State.THINKING
                        return State.THINKING
                    # case it is parsing @
                    self.__count += 1
                    return State.IDLE
                else:
                    self.__count = 0
                    return State.SPEAKING
            case State.THINKING:
                if c == '@':
                    # case it reached three @
                    if self.__count == 2:
                        self.__count = 0
                        self.__state = State.SPEAKING
                        return State.IDLE
                    # case it is parsing #
                    self.__count += 1
                    return State.IDLE
                else:
                    self.__count = 0
                    return State.THINKING


class DefaultArchitecture:

    def __init__(
            self,
            llm: LLM,
            router_prompt: str,
            general_prompt: str,
            reasoning_prompt: str,
    ):
        self.llm: LLM = llm
        self.memory: Memory = Memory()
        self.__router_prompt: str = router_prompt
        self.__general_prompt: str = general_prompt
        self.__reasoning_prompt: str = reasoning_prompt

        self.__thought_parser = State()

    def query(self, session_id: int, user_input: str):
        # Add user input to the conversation
        # create a new conversation if not exists
        if not self.memory.get_session(session_id):
            print('[+] Creating new session')
            self.memory.store_message(
                session_id,
                Message(
                    role=Role.SYS,
                    content=self.__general_prompt
                )
            )

        # ROUTING
        route_messages = [
            {'role': 'system', 'content': self.__router_prompt},
            {'role': 'user', 'content': user_input}
        ]
        assistant_index = 1
        assistant_index_buffer = ''
        for chunk, _ in self.llm.query(route_messages):
            if not chunk:
                break
            assistant_index_buffer += chunk
        try:
            assistant_index = int(assistant_index_buffer.strip()[:1])
        except ValueError:
            print(
                f'[!] Wrong assistant index: {assistant_index_buffer}'
            )

        # RESPONSE
        prompt = self.__general_prompt
        if assistant_index == 2:
            prompt = self.__reasoning_prompt

        history = self.memory.get_session(session_id)
        history.messages[0] = Message(role=Role.SYS, content=prompt)
        history.add_message(
            Message(
                role=Role.USER,
                content=user_input
            )
        )

        # note: history.message_dict doesn't care about context length
        print(f'> ({assistant_index}) Assistant: ')
        response = ''
        for chunk, ctx_length in self.llm.query(history.message_dict):
            if ctx_length:
                break
            if assistant_index == 1:
                response += chunk
                yield chunk
                continue

            for c in chunk:
                generation_state = self.__thought_parser.state(c)
                if generation_state == State.SPEAKING:
                    yield c


if __name__ == "__main__":
    mistral = LLM(
        model='mistral:7b-instruct-v0.3-q8_0',
        inference_endpoint='https://323a-34-125-86-173.ngrok-free.app/',
    )
    assistant = DefaultArchitecture(
        llm=mistral,
        router_prompt=ROUTER,
        general_prompt=GENERAL,
        reasoning_prompt=REASONING
    )

    while True:
        usr_input = input('\n> User: ')
        if usr_input == '-1':
            break
        else:
            for ch in assistant.query(0, usr_input):
                print(ch, end='')
