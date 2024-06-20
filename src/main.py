from src import upload_knowledge
from src.agent import Agent
from src.agent.tools import TOOLS
from src.agent.knowledge import Store


# Enter: new 1
# Enter: rename plan_no_rag
# Enter: save 1
# Hi, we need to plan the Reconnaissance phase for the website example.com
# I need to ensure that the user credentials are safe from hackers, so my objective is to ensure there are no database
# vulnerabilities, cross-site scripting vulnerabilities and ways to access the host for the server. so for the current
# phase our objective is to gain as much information as possible

# TODO: how do we provide output of one task to another? how to manage task dependencies?

def cli_test():
    """testing Agent"""
    ollama_model = 'llama3'
    tools_documentation = '\n'.join([tool.get_documentation() for tool in TOOLS])

    vector_db = Store()
    upload_knowledge('../data/json', vector_db)

    # =================================================================
    agent = Agent(model=ollama_model, tools_docs=tools_documentation, knowledge_base=vector_db)
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

        elif user_input.split(" ")[0] == "rename":  # rename session
            agent.rename_session(current_session, user_input.split(" ")[1])

        else:  # query
            for chunk in agent.query(current_session, user_input, rag=False):
                print(chunk, end='')
            print()


if __name__ == "__main__":
    cli_test()
