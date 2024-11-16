"""
Contains the classes that represent Memory.
"""
import json
import logging
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Dict, List

SESSIONS_PATH = Path(Path.home() / '.aiops' / 'sessions')
if not SESSIONS_PATH.exists():
    SESSIONS_PATH.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger(__name__)

formatter = logging.Formatter('%(levelname)s: %(name)s: %(message)s')

logger_handler = logging.StreamHandler()
logger_handler.setLevel(logging.DEBUG)
logger_handler.setFormatter(formatter)

logger.setLevel(logging.DEBUG)
logger.addHandler(logger_handler)


class Role(StrEnum):
    """Message role"""
    SYS = 'system'
    USER = 'user'
    ASSISTANT = 'assistant'
    TOOL = 'tool'

    @staticmethod
    def from_str(item):
        """Convert a string role to Role"""
        if item == 'user':
            return Role.USER
        if item == 'assistant':
            return Role.ASSISTANT
        if item == 'system':
            return Role.SYS
        if item == 'tool':
            return Role.TOOL
        return None


@dataclass
class Message:
    """Message object"""
    role: Role
    content: str


@dataclass
class Session:
    """Represents a conversation"""
    name: str
    messages: List[Message]
    _tokens: int = 0

    def add_message(self, message: Message):
        """Append a message"""
        if not isinstance(message, Message):
            raise ValueError(f'Not a message: {message}')
        self.messages.append(message)

    @property
    def message_dict(self):
        return [
            {'role': str(msg.role), 'content': msg.content}
            for msg in self.messages
        ]

    @property
    def tokens(self):
        return self._tokens

    @tokens.setter
    def tokens(self, val):
        self._tokens = val

    @staticmethod
    def from_json(path: str):
        """Get a session from a JSON file"""
        try:
            with open(str(path), 'r', encoding='utf-8') as fp:
                data = json.load(fp)
        except json.decoder.JSONDecodeError:
            return -1, None

        session = Session(
            name=data['name'],
            messages=[
                Message(Role.from_str(msg['role']), msg['content'])
                for msg in data['messages']
            ],
        )

        return data['id'], session


class Memory:
    """
    Contains the chat history for each session.
    """

    def __init__(self):
        self.sessions: Dict[int: Session] = {}
        self.load_sessions()

    def store_message(self, sid: int, message: Message):
        """Add a message to a session identified by session id.
        Creates a new session if the specified do not exist."""
        if sid not in self.sessions:
            self.sessions[sid] = Session(name='New Session', messages=[])
        self.sessions[sid].add_message(message)

    def get_session(self, sid: int) -> Session:
        """
        :return: a session identified by session id or None
        """
        return self.sessions[sid] if sid in self.sessions else None

    def replace_system_prompt(self, sid: int, message: Message):
        session = self.sessions[sid]
        session.messages[0] = message

    def get_sessions(self) -> dict:
        """Returns all loaded sessions as id: session"""
        return self.sessions

    def save_session(self, sid: int):
        """Saves the current session state to a JSON file at SESSION_PATH"""
        if sid not in self.sessions:
            raise ValueError(f'Session {sid} does not exist')

        session: Session = self.sessions[sid]
        self.delete_session(sid)

        path = f'{SESSIONS_PATH}/{sid}__{session.name}.json'
        with open(path, 'w+', encoding='utf-8') as fp:
            data = {
                'id': sid,
                'name': session.name,
                'messages': session.message_dict,
            }
            json.dump(data, fp)

    def delete_session(self, sid: int):
        """Deletes a session from SESSION_PATH"""
        if sid not in self.sessions:
            raise ValueError(f'Session {sid} does not exist')

        for path in SESSIONS_PATH.iterdir():
            if path.is_file() and path.suffix == '.json' and \
                    path.name.startswith(f'{sid}__'):
                path.unlink()

    def rename_session(self, sid: int, session_name: str):
        """Renames a session identified by session id or creates a new one"""
        if sid not in self.sessions:
            self.sessions[sid] = Session(name=session_name, messages=[])
        else:
            self.sessions[sid].name = session_name

    def load_sessions(self):
        """Loads the saved sessions at SESSION_PATH"""
        for path in SESSIONS_PATH.iterdir():
            if path.is_file() and path.suffix == '.json':
                sid, session = Session.from_json(str(path))
                if sid == -1:
                    logger.error(f"Failed loading session {path}")
                logger.info(f"Loaded session {path}")
                self.sessions[sid] = session
