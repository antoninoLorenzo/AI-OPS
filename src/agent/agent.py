from src.agent.llm import LLM
from src.agent.plan import Plan
from src.agent.memory import Memory, Message, Role
from src.agent.prompts import PROMPTS


class Agent:
    def __init__(self, model: str, tools_docs):
        self.llm = LLM(model=model)
        self.mem = Memory()
        self.system_prompt = 'You are an assistant.'  # PROMPTS[ollama_model]['system']['plan'].format(tools=tools_docs)
        self.user_prompt = PROMPTS[model]['user']['plan']

    def new_session(self, sid: int):
        self.mem.store_message(sid, Message(Role.SYS, self.system_prompt))

    def get_session(self, sid: int):
        return self.mem.get_session(sid)

    def query(self, sid: int, user_in: str):
        self.mem.store_message(
            sid,
            Message(Role.USER, self.user_prompt.format(user_input=user_in))
        )
        messages = self.mem.get_session(sid).messages_to_dict_list()

        response = ''
        for chunk in self.llm.query(messages):
            yield chunk['message']['content']
            response += chunk['message']['content']

        self.mem.store_message(
            sid,
            Message(Role.ASSISTANT, response)
        )

    def save_session(self, sid: int):
        self.mem.save_session(sid)

    def delete_session(self, sid: int):
        self.mem.delete_session(sid)

    def rename_session(self, sid: int, session_name: str):
        self.mem.rename_session(sid, session_name)
