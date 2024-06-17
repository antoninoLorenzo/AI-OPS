import json
from src.agent import Agent
from src.agent.tools import TOOLS
from src.agent.knowledge import Store
from src.agent.knowledge import Collection, Document, Topic


def cli_test():
    """testing Agent"""
    ollama_model = 'gemma:2b'
    tools_documentation = '\n'.join([tool.get_documentation() for tool in TOOLS])

    vector_db = Store()
    web_pt = Collection(
        id=1,
        title='Web Penetration Testing',
        documents=[],
        topics=[Topic.WebPenetrationTesting],
    )
    vector_db.create_collection(web_pt)

    with open('../data/json/owasp.json', 'r', encoding='utf-8') as file:
        owasp_data = json.load(file)

    for ow_data in owasp_data:
        vector_db.upload(Document(
            name=ow_data['title'],
            content=ow_data['content'],
            topic=None
        ), web_pt.title)

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
            for chunk in agent.query(current_session, user_input):
                print(chunk, end='')
            print()


if __name__ == "__main__":
    cli_test()
