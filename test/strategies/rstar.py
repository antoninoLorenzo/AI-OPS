import time
from concurrent.futures import (
    ThreadPoolExecutor,
    ProcessPoolExecutor,
    as_completed
)

from src.agent.llm import Ollama


llm = Ollama(
    model='mistral:7b-instruct-v0.3-q8_0',
    inference_endpoint='https://73fc-34-16-255-93.ngrok-free.app/',
)


def query_wrapper(user_input: str):
    res = ''
    for ch, _ in llm.query([{'role': 'user', 'content': user_input}]):
        res += ch
    return res


if __name__ == '__main__':
    pass


