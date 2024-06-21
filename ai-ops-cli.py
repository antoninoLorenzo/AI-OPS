"""
CLI Client for the Agent API, is useful for development and
when executing the frontend is not convenient.

"""
import sys

import requests


class AgentClient:
    """Client for Agent API"""
    # TODO: add help

    def __init__(self, api_url: str = 'http://127.0.0.1:8000'):
        self.api_url = api_url
        self.client = requests.Session()
        self.current_session = {'sid': 0, 'name': 'Undefined'}
        self.commands = {
            'chat': self.chat,
            'new': self.new_session,
            'save': self.save_session,
            'rename': self.rename_session,
            'delete': self.delete_session,
            'list': self.list_sessions,
            'load': self.load_session
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

    def new_session(self):
        """Creates a new session and opens the related chat"""
        session_name = input('Session Name: ')

        response = self.client.get(
            f'{self.api_url}/session/new',
            params={'name': session_name}
        )
        response.raise_for_status()

        self.current_session = {'sid': response.json()['sid'], 'name': session_name}
        self.chat()

    def save_session(self):
        """Save the current session"""
        response = self.client.get(
            f'{self.api_url}/session/{self.current_session["sid"]}/save'
        )
        if response.status_code != 200:
            print(f'[!] Failed: {response.status_code}')
        else:
            print(f'[+] Saved')
        self.chat()

    def rename_session(self):
        """Renames the current session"""
        session_name = input('New Name: ')

        response = self.client.get(
            f'{self.api_url}/session/{self.current_session["sid"]}/rename',
            params={'new_name': session_name}
        )
        response.raise_for_status()
        self.current_session['name'] = session_name
        self.chat()

    def delete_session(self):
        """Deletes the current session"""
        response = self.client.get(
            f'{self.api_url}/session/{self.current_session["sid"]}/delete'
        )
        response.raise_for_status()
        body = response.json()
        print(f'[{"+" if body["success"] else "-"}] {body["message"]}')

    def list_sessions(self):
        """List all sessions"""
        response = self.client.get(
            f'{self.api_url}/session/list/'
        )
        response.raise_for_status()
        body = response.json()
        if len(body) == 0:
            print('[+] No sessions found')
        else:
            print(f'[+] Available Sessions: ')
            for session in body:
                print(f'| - ({session["sid"]}) {session["name"]}')

    def load_session(self):
        """Opens an existing session"""
        session_id = input('Enter session id: ')
        if not session_id.isdigit():
            print('[-] Not a number')
            self.load_session()

        response = self.client.get(
            f'{self.api_url}/session/get/',
            params={'sid': int(session_id)}
        )
        response.raise_for_status()

        body = response.json()
        self.current_session = {'sid': body['sid'], 'name': body['name']}
        print(f'+ {self.current_session["name"]} ({self.current_session["sid"]})')

        for msg in body['messages']:
            print(f'{msg["role"]}: {msg["content"]}\n')
        self.chat(print_name=False)

    def chat(self, print_name=True):
        """Opens a chat with the Agent"""
        if print_name:
            print(f'+ {self.current_session["name"]} ({self.current_session["sid"]})')
        query_url = f'{self.api_url}/session/{self.current_session["sid"]}/query'
        while True:
            q = input('user: ')
            if q == '-1':
                break

            with self.client.get(
                    query_url,
                    params={'q': q},
                    headers=None,
                    stream=True) as resp:
                print('assistant: ')
                for chunk in resp.iter_content():
                    if chunk:
                        print(chunk.decode(), end='')
                print()


if __name__ == "__main__":
    # TODO: define arguments (eg. api_url, database_url, etc.)
    try:
        client = AgentClient()
        client.run()
    except KeyboardInterrupt:
        sys.exit()
