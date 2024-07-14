"""Contains the class `Agent`, the core of the system."""
import re
import json
from json import JSONDecodeError

from src.agent.knowledge import Store
from src.agent.llm import LLM, AVAILABLE_PROVIDERS
from src.agent.memory import Memory, Message, Role
from src.agent.plan import Plan, Task
from src.agent.prompts import PROMPTS
from src.agent.tools import Terminal


class Agent:
    """Penetration Testing Assistant"""

    def __init__(self, model: str,
                 tools_docs: str = '',
                 knowledge_base: Store = None,
                 llm_endpoint: str = 'http://localhost:11434',
                 provider: str = 'ollama',
                 provider_key: str = ''):
        # Pre-conditions
        if provider not in AVAILABLE_PROVIDERS.keys():
            raise RuntimeError(f'{provider} not supported.')

        provider_class = AVAILABLE_PROVIDERS[provider]['class']
        key_required = AVAILABLE_PROVIDERS[provider]['key_required']
        if key_required and len(provider_key) == 0:
            raise RuntimeError(f'{provider} requires an api key, set PROVIDER_KEY environment variable.')

        # Agent Components
        self.llm = LLM(
            model=model,
            client_url=llm_endpoint,
            provider_class=provider_class,
            api_key=provider_key
        )
        self.mem = Memory()
        self.vdb: Store | None = knowledge_base

        # Prompts
        self._available_tools = tools_docs
        self.system_plan_gen = PROMPTS[model]['plan']['system'].format(
            tools=self._available_tools
        )
        self.user_plan_gen = PROMPTS[model]['plan']['user']
        self.system_plan_con = PROMPTS[model]['plan_conversion']['system']
        self.user_plan_con = PROMPTS[model]['plan_conversion']['user']

    def query(self, sid: int, user_in: str, rag=True):
        """Performs a query to the Large Language Model,
        set `rag=True` to leverage Retrieval Augmented Generation."""
        if rag:
            context = self._retrieve(user_in)
            prompt = self.user_plan_gen.format(
                user_input=user_in,
                context=context
            )
        else:
            prompt = '\n'.join(self.user_plan_gen.split('\n')[:-3])
            prompt = prompt.format(user_input=user_in)

        # ensure session is initialized (otherwise llm has no system prompt)
        if sid not in self.mem.sessions.keys():
            self.new_session(sid)

        self.mem.store_message(
            sid,
            Message(Role.USER, prompt)
        )
        messages = self.mem.get_session(sid).messages_to_dict_list()

        # generate response
        response = ''
        # prompt_tokens = 0
        response_tokens = 0
        for chunk in self.llm.query(messages):
            # if chunk['done']:
            #     prompt_tokens = chunk['prompt_eval_count'] if 'prompt_eval_count' in chunk else None
            #     response_tokens = chunk['eval_count']
            yield chunk  # ['message']['content']

            response += chunk  # ['message']['content']

        # self.mem.get_session(sid).messages[-1].tokens = prompt_tokens
        self.mem.store_message(
            sid,
            Message(Role.ASSISTANT, response, tokens=response_tokens)
        )

    def new_session(self, sid: int):
        """Initializes a new conversation"""
        self.mem.store_message(sid, Message(Role.SYS, self.system_plan_gen))

    def get_session(self, sid: int):
        """Open existing conversation"""
        return self.mem.get_session(sid)

    def get_sessions(self):
        """Returns list of Session objects"""
        return self.mem.get_sessions()

    def save_session(self, sid: int):
        """Saves the specified session to JSON"""
        self.mem.save_session(sid)

    def delete_session(self, sid: int):
        """Deletes the specified session"""
        self.mem.delete_session(sid)

    def rename_session(self, sid: int, session_name: str):
        """Rename the specified session"""
        self.mem.rename_session(sid, session_name)

    def extract_plan(self, plan_nl):
        """Converts a structured LLM response in a Plan object"""
        prompt = self.user_plan_con.format(query=plan_nl)
        messages = [
            {'role': 'system', 'content': self.system_plan_con},
            {'role': 'user', 'content': prompt}
        ]
        stream = self.llm.query(messages=messages)
        response = ''
        for chunk in stream:
            response += chunk

        try:
            plan_data = json.loads(response)
        except JSONDecodeError:
            # try extracting json from response
            json_regex = re.compile(r'\[.*?\]', re.DOTALL)
            json_match = json_regex.search(response)
            if json_match:
                plan_data = json.loads(json_match.group())
            else:
                print(f'PlanError:\n{response}')
                return None

        if not plan_data:
            raise RuntimeError(f'Error extracting plan: data not found.'
                               f'\nResponse: {response}')

        tasks = []
        for task in plan_data:
            if 'command' not in task.keys() or len(task['command']) == 0:
                continue
            if task['command'] == 'N/A':
                continue
            if task['command'].startswith('`'):
                cmd = task['command'][1:-1]
            else:
                cmd = task['command']

            tasks.append(Task(
                command=cmd,
                thought=task['thought'] if 'thought' in task else None,
                tool=Terminal
            ))

        return Plan(tasks)

    def execute_plan(self, sid):
        """Extracts the plan from last message,
        stores it in memory and executes it."""
        messages = self.mem.get_session(sid).messages
        if len(messages) <= 1:
            return None

        msg = messages[-1] if messages[-1].role == Role.ASSISTANT else messages[-2]

        try:
            plan = self.extract_plan(msg.content)
        except Exception as err:
            raise RuntimeError(err)

        yield from plan.execute()

        self.mem.store_plan(sid, plan)

    def _retrieve(self, user_in: str):
        """Get context from Qdrant"""
        if not self.vdb:
            raise RuntimeError('RAG is not initialized')
        context = ''
        for retrieved in self.vdb.retrieve(user_in):
            context += (f"{retrieved.payload['title']}:"
                        f"\n{retrieved.payload['text']}\n\n")
        return context
