from src.agent import Agent
from src.agent.tools import TOOLS


def cli_test():
    """testing Agent"""
    ollama_model = 'gemma:2b'
    tools_documentation = '\n'.join([tool.get_documentation() for tool in TOOLS])

    agent = Agent(model=ollama_model, tools_docs=tools_documentation)
    current_session = 0
    while True:
        user_input = input("Enter: ")
        if user_input == "-1":
            break
        elif user_input == "exec":  # execute plan
            pass

        elif user_input.split(" ")[0] == "new":  # create session
            agent.new_session(int(user_input.split(" ")[1]))
            current_session = int(user_input.split(" ")[1])

        elif user_input.split(" ")[0] == "save":  # save session
            agent.save_session(int(user_input.split(" ")[1]))

        elif user_input.split(" ")[0] == "load":  # load session
            current_session = int(user_input.split(" ")[1])
            session_history = agent.get_session(current_session)
            for msg in session_history.messages_to_dict_list():
                print(f'\n> {msg["role"]}: {msg["content"]}')

        else:  # query
            for chunk in agent.query(current_session, user_input):
                print(chunk, end='')
            print()


if __name__ == "__main__":
    pass
