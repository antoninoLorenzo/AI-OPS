"""
CLI Client for the Agent API, is useful for development and
when executing the frontend is not convenient.

"""
import sys

import requests


current_session = {'sid': 0, 'name': 'Undefined'}


def new_session(s: requests.Session, url: str = 'http://127.0.0.1:8000'):
    """"""
    global current_session
    session_name = input('Session Name: ')
    response = s.get(f'{url}/session/new', params={'name': session_name})
    response.raise_for_status()
    current_session = {'sid': response.json()['sid'], 'name': session_name}


def chat(s: requests.Session, url: str = 'http://127.0.0.1:8000'):
    """"""
    print(f'+ {current_session["name"]} ({current_session["sid"]})')
    query_url = f'{url}/session/{current_session["sid"]}/query'
    while True:
        q = input('User: ')
        if q == '-1':
            break

        with s.get(query_url, params={'q': q}, headers=None, stream=True) as resp:
            print('Assistant: ')
            for chunk in resp.iter_content():
                if chunk:
                    print(chunk.decode(), end='')
            print()


commands = {
    'chat': chat,
    'new': new_session,
    'save': '',
    'rename': '',
    'delete': '',
    'list': '',
    'load': ''
}


def main():
    """"""
    client = requests.Session()

    while True:
        user_input = input("> ")
        user_input = user_input.strip()
        if user_input == 'bye':
            break

        if user_input not in commands.keys():
            print("Invalid Input")
            continue

        commands[user_input](client)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit()
