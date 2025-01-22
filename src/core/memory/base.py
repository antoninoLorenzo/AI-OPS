import json
from pathlib import Path
from typing import Dict

from pydantic import validate_call
from src.core.memory.schema import Message, Conversation
from src.utils import get_logger


logger = get_logger(__name__)

SESSIONS_PATH = Path(Path.home() / '.aiops' / 'sessions')
if not SESSIONS_PATH.exists():
    SESSIONS_PATH.mkdir(parents=True, exist_ok=True)
    logger.info(f"\tCreated {str(SESSIONS_PATH)}")


class Memory:
    """
    Contains the chat history for each session.
    """

    def __init__(self):
        self.sessions: Dict[int: Conversation] = {}
        self.load_conversations()

    @validate_call
    def store_message(self, sid: int, message: Message):
        """Add a message to a session identified by session id.
        Creates a new session if the specified do not exist."""
        if sid not in self.sessions:
            self.sessions[sid] = Conversation(name='New Session', messages=[])
        self.sessions[sid].add(message)

    def get_conversation(self, sid: int) -> Conversation:
        """
        :return: a session identified by session id or None
        """
        return self.sessions[sid] if sid in self.sessions else None

    @validate_call
    def replace_system_prompt(self, sid: int, message: Message):
        session = self.sessions[sid]
        session.messages[0] = message

    def get_conversations(self) -> dict:
        """Returns all loaded sessions as id: session"""
        return self.sessions

    def save_conversation(self, sid: int):
        """Saves the current session state to a JSON file at SESSION_PATH"""
        if sid not in self.sessions:
            logger.error(f'\tError in {self.__name__}: session not exists.')
            raise ValueError(f'Session {sid} does not exist')

        session: Conversation = self.sessions[sid]
        self.delete_conversation(sid)

        path = f'{SESSIONS_PATH}/{sid}__{session.name}.json'
        with open(path, 'w+', encoding='utf-8') as fp:
            try:
                data = {
                    'id': sid,
                    'name': session.name,
                    'messages': session.model_dump(),
                }
                json.dump(data, fp, indent='\t')
            except (
                UnicodeDecodeError,
                json.JSONDecodeError,
                OverflowError
            ) as save_error:
                logger.error(
                    f'Failed saving session {sid}. {save_error}'
                )

    def delete_conversation(self, sid: int):
        """Deletes a session from SESSION_PATH"""
        # TODO: should also delete session from sessions dictionary
        if sid not in self.sessions:
            raise ValueError(f'Session {sid} does not exist')

        # delete file from ~/.aiops/sessions
        for path in SESSIONS_PATH.iterdir():
            if path.is_file() and path.suffix == '.json' and \
                    path.name.startswith(f'{sid}__'):
                path.unlink()

        # delete session from memory
        self.sessions.pop(sid, None)

    def rename_conversation(self, sid: int, session_name: str):
        """Renames a session identified by session id or creates a new one"""
        if sid not in self.sessions:
            self.sessions[sid] = Conversation(name=session_name, messages=[])
        else:
            self.sessions[sid].name = session_name

    def load_conversations(self):
        """Loads the saved sessions at SESSION_PATH"""
        for path in SESSIONS_PATH.iterdir():
            if path.is_file() and path.suffix == '.json':
                sid, session = Conversation.from_json(str(path))
                if sid == -1:
                    logger.error(f"\tFailed loading session {path}")
                logger.info(f"\tLoaded session {path}")
                self.sessions[sid] = session
