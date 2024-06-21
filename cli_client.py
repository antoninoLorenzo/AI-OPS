"""
CLI Client for the Agent API, is useful for development and
when executing the frontend is not convenient.

"""
import sys

import requests


class AgentClient:
    """Client for Agent API"""

    def __init__(self, api_url: str = 'http://127.0.0.1:8000'):
        self.api_url = api_url
        self.client = requests.Session()
        self.current_session = {'sid': 0, 'name': 'Undefined'}
        self.commands = {
            'chat': self.chat,
            'new': self.new_session,
            'save': '',
            'rename': '',
            'delete': '',
            'list': '',
            'load': ''
        }

    def run(self):
        """Runs the main loop of the client"""
        while True:
            user_input = input("> ")
            user_input = user_input.strip()
            if user_input == 'bye':
                break

            if user_input not in self.commands.keys():
                print("Invalid Input")
                continue

            self.commands[user_input]()

    def new_session(self, url: str = 'http://127.0.0.1:8000'):
        """Creates a new session and opens the related chat"""
        session_name = input('Session Name: ')

        response = self.client.get(
            f'{self.api_url}/session/new',
            params={'name': session_name}
        )
        response.raise_for_status()

        self.current_session = {'sid': response.json()['sid'], 'name': session_name}
        self.chat()

    def chat(self):
        """Opens a chat with the Agent"""
        print(f'+ {self.current_session["name"]} ({self.current_session["sid"]})')
        query_url = f'{self.api_url}/session/{self.current_session["sid"]}/query'
        while True:
            q = input('User: ')
            if q == '-1':
                break

            with self.client.get(
                    query_url,
                    params={'q': q},
                    headers=None,
                    stream=True) as resp:
                print('Assistant: ')
                for chunk in resp.iter_content():
                    if chunk:
                        print(chunk.decode(), end='')
                print()


if __name__ == "__main__":
    try:
        client = AgentClient()
        client.run()
    except KeyboardInterrupt:
        sys.exit()
