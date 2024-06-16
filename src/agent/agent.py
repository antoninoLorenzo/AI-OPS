from src.agent.llm import LLM
from src.agent.plan import Plan
from src.agent.prompts import PROMPTS
from src.agent.tools import TOOLS


class Agent:
    pass


if __name__ == "__main__":
    model = 'gemma:2b'
    llm = LLM(model=model)
    tools_documentation = '\n'.join([tool.get_documentation() for tool in TOOLS])

    sys_prompt = PROMPTS[model]['system']['plan'].format(tools=tools_documentation)
    usr_prompt = ''

    while True:
        user_input = input("Enter: ")
        if user_input == "-1":
            break
        elif user_input == "exec":
            pass  # execute plan
        else:
            pass  # make query
