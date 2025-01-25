import json
from pathlib import Path
from typing import Dict

from pydantic import validate_call
from src.core.memory.schema import Conversation
from src.utils import get_logger


logger = get_logger(__name__)

SESSIONS_PATH = Path(Path.home() / '.aiops' / 'sessions')
if not SESSIONS_PATH.exists():
    SESSIONS_PATH.mkdir(parents=True, exist_ok=True)
    logger.info(f"\tCreated {str(SESSIONS_PATH)}")


class Memory:
    """Manages in-memory conversations and provides persistence.

    Conversations are accessible via Python mapping protocol (`memory[key]`).

    Conversations can be saved to persistent JSON files and will be
    loaded on Memory initialization.

    # TODO: Implement conversation management for max context length
    """

    def __init__(self):
        self.__conversation_map: Dict[int: Conversation] = {}
        self.__load_conversations()

    @validate_call
    def __setitem__(self, key, value: Conversation):
        self.__conversation_map[key] = value

    def __getitem__(self, key) -> Conversation:
        return self.__conversation_map[key] \
            if key in self.__conversation_map \
            else None

    def __contains__(self, key):
        return key in self.__conversation_map

    @property
    def conversations(self) -> Dict[int, Conversation]:
        return self.__conversation_map

    def save(self, conversation_id: int):
        """Saves a conversation to a persistent JSON file in SESSION_PATH.
        In the case `conversation_id` is not in memory, the error is logged.
        """
        if conversation_id not in self:
            logger.error(f'[save]: {conversation_id} not available.')
            return

        conversation = self.__conversation_map[conversation_id]
        conversation_path = (
            SESSIONS_PATH
            / f'{conversation_id}__{conversation.name}.json'
        )
        with open(str(conversation_path), 'w+', encoding='utf-8') as fp:
            try:
                data = {
                    'id': conversation_id,
                    'name': conversation.name,
                    'messages': conversation.model_dump(),
                }
                json.dump(data, fp, indent='\t')
            except Exception as save_error:
                logger.error(
                    f'[save]: failed saving conversation {conversation_id}. {save_error}'
                )

    def delete(self, conversation_id: int):
        """Removes Conversation object from internal map and from persistent
        files. In case `conversation_id` is not in memory, the error is logged.
        """
        if conversation_id not in self:
            logger.error(f'[delete]: {conversation_id} not available.')
            return

        conversation_path = (
            SESSIONS_PATH
            / f'{conversation_id}__{self[conversation_id].name}.json'
        )
        if conversation_path.exists():
            conversation_path.unlink()
            self.__conversation_map.pop(conversation_id, None)
        else:
            logger.error(f'[delete]: {conversation_path} not found.')

    def __load_conversations(self):
        """
        Populates the internal map from persistent JSON files at SESSION_PATH.
        """
        for path in SESSIONS_PATH.iterdir():
            if path.is_file() and path.suffix == '.json':
                sid, session = Conversation.from_json(str(path))
                if sid == -1:
                    logger.error(f"\tFailed loading session {path}")
                logger.info(f"\tLoaded session {path}")
                self.__conversation_map[sid] = session
