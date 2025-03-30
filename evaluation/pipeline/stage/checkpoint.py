import time
from pathlib import Path

import joblib

from src.core.memory import Conversation, Message, Role


def main():
    checkpoint_path = Path('inference_checkpoints')
    payload = 'import os; print(os.environ.get("PATH"), "not_found")'
    conversation = Conversation(
        conversation_id=1,
        name='untitled',
        messages=[
            Message(role=Role.ASSISTANT, content=payload)
        ]
    )

    joblib.dump(conversation, str(checkpoint_path))
    print('dump')

    time.sleep(2)

    checkpoint = joblib.load(str(checkpoint_path))
    print(checkpoint)

if __name__ == "__main__":
    main()

