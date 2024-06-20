"""Contains the class `Agent`, the core of the system."""
from src.agent.llm import LLM
from src.agent.knowledge import Store
from src.agent.memory import Memory, Message, Role
from src.agent.prompts import PROMPTS


class Agent:
    """Penetration Testing Assistant"""
    def __init__(self, model: str, tools_docs: str, knowledge_base: Store):
        self.llm = LLM(model=model)
        self.mem = Memory()
        self.vdb = knowledge_base
        # PROMPTS[model]['system']['plan'].format(tools=tools_docs)
        self.system_prompt = 'You are an assistant in penetration testing'
        self.user_prompt = PROMPTS[model]['plan']['user']

    def new_session(self, sid: int):
        self.mem.store_message(sid, Message(Role.SYS, self.system_prompt))

    def get_session(self, sid: int):
        return self.mem.get_session(sid)

    def query(self, sid: int, user_in: str, rag=True):
        """Performs a query to the Large Language Model, set `rag=True`
        to leverage Retrieval Augmented Generation."""
        context = ''
        if rag:
            context = self._retrieve(user_in)

        # user prompt
        prompt = self.user_prompt.format(user_input=user_in, context=context)
        self.mem.store_message(
            sid,
            Message(Role.USER, prompt)
        )
        messages = self.mem.get_session(sid).messages_to_dict_list()

        # generate response
        response = ''
        for chunk in self.llm.query(messages):
            yield chunk['message']['content']
            response += chunk['message']['content']

        self.mem.store_message(
            sid,
            Message(Role.ASSISTANT, response)
        )

    def _retrieve(self, user_in: str):
        """Get context from Qdrant"""
        context = ''
        for retrieved in self.vdb.retrieve(user_in):
            context += (f"{retrieved.payload['title']}:"
                        f"\n{retrieved.payload['text']}\n\n")
        return context

    def save_session(self, sid: int):
        """Saves the specified session to JSON"""
        self.mem.save_session(sid)

    def delete_session(self, sid: int):
        """Deletes the specified session"""
        self.mem.delete_session(sid)

    def rename_session(self, sid: int, session_name: str):
        """Rename the specified session"""
        self.mem.rename_session(sid, session_name)


if __name__ == '__main__':
    from src.agent.knowledge.routing import LLMRouter

    vector_db = Store(router=LLMRouter())
    agent = Agent(model='gemma:2b', tools_docs='', knowledge_base=vector_db)

    user_query = 'what are most common authentication issues in websites?'
    # user_query = 'How do I perform host discovery with nmap?'

    for chunk in agent.query(1, user_query):
        print(chunk, end='')
    print()
