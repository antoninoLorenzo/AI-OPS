from src.agent.llm import LLM
from src.agent.knowledge import Store
from src.agent.memory import Memory, Message, Role
from src.agent.prompts import PROMPTS


class Agent:
    def __init__(self, model: str, tools_docs: str, knowledge_base: Store):
        self.llm = LLM(model=model)
        self.mem = Memory()
        self.vdb = knowledge_base
        self.system_prompt = 'You are an assistant.'  # PROMPTS[ollama_model]['system']['plan'].format(tools=tools_docs)
        self.user_prompt = PROMPTS[model]['user']['plan']

    def new_session(self, sid: int):
        self.mem.store_message(sid, Message(Role.SYS, self.system_prompt))

    def get_session(self, sid: int):
        return self.mem.get_session(sid)

    def query(self, sid: int, user_in: str):
        # retrieval
        i = 0
        collection_name = ''
        for c_name, _ in self.vdb.collections.items():
            if i >= 1:
                break
            collection_name = c_name
            i += 1
        context = ''
        for retrieved in self.vdb.retrieve(user_in, collection_name):
            context += retrieved.payload['text']

        # user prompt
        self.mem.store_message(
            sid,
            Message(Role.USER, self.user_prompt.format(user_input=user_in, context=context))
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

    def save_session(self, sid: int):
        """Saves the specified session to JSON"""
        self.mem.save_session(sid)

    def delete_session(self, sid: int):
        """Deletes the specified session"""
        self.mem.delete_session(sid)

    def rename_session(self, sid: int, session_name: str):
        """Rename the specified session"""
        self.mem.rename_session(sid, session_name)
