"""
Interfaces the AI Agent to the LLM Provider, model availability depends on
implemented prompts, to use a new model the relative prompts should be written.
"""
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import requests.exceptions
from requests import Session
from ollama import Client
from ollama._types import ResponseError

AVAILABLE_MODELS = {
    'llama3': {
        'options': {
            'temperature': 0.5,
            'num_ctx': 8192
        }
    },
    'gemma:7b': {
        'options': {
            'temperature': 0.5,
            'num_ctx': 8192
        }
    },
    'mistral': {
        'options': {
            'temperature': 0.5,
            'num_ctx': 8192
        }
    },
    'phi3': {
        'options': {
            'temperature': 0.5,
            'num_ctx': 8192
        }
    },
}


@dataclass
class Provider(ABC):
    """Represents a LLM Provider"""
    model: str
    client_url: str = 'http://localhost:11434'
    api_key: str | None = None

    @abstractmethod
    def query(self, messages: list, stream=True):
        """Implement to makes query to the LLM provider"""


@dataclass
class Ollama(Provider):
    """Ollama Interface"""
    client: Client | None = field(init=False, default=None)

    def __post_init__(self):
        if self.model not in AVAILABLE_MODELS.keys():
            raise ValueError(f'Model {self.model} is not available')
        self.client = Client(self.client_url)

    def query(self, messages: list, stream=True):
        """Generator that returns response chunks."""
        try:
            stream = self.client.chat(
                model=self.model,
                messages=messages,
                stream=stream,
                options=AVAILABLE_MODELS[self.model]['options']
            )
            for chunk in stream:
                yield chunk['message']['content']
        except ResponseError as err:
            raise RuntimeError(err)


@dataclass
class OpenRouter(Provider):
    """OpenRouter Interface"""
    session: Session | None = None

    def __post_init__(self):
        self.session = Session()
        self.models = {
            'gemma:7b': 'google/gemma-2-9b-it:free',
            'mistral': 'mistralai/mistral-7b-instruct:free'
        }

    def query(self, messages: list, stream=True):
        """Generator that returns response chunks."""
        response = self.session.post(
                url=self.client_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "HTTP-Referer": 'https://github.com/antoninoLorenzo/AI-OPS',
                    "X-Title": 'AI-OPS',
                },
                data=json.dumps({
                    "model": self.models[self.model],
                    "messages": messages,
                    # 'stream': True how the fuck works
                })
        )

        try:
            response.raise_for_status()
            output = json.loads(response.text)['choices'][0]['message']['content']
        except requests.exceptions.HTTPError as req_err:
            raise RuntimeError(req_err)
        except json.JSONDecodeError as js_err:
            raise RuntimeError(f'Internal Error: {js_err}')

        return output


@dataclass
class LLM:
    """LLM interface"""
    model: str
    client_url: str = 'http://localhost:11434'
    provider: Provider = None
    provider_class: Provider = Ollama
    api_key: str | None = None

    def __post_init__(self):
        self.provider = self.provider_class(
            model=self.model,
            client_url=self.client_url,
            api_key=self.api_key
        )

    def query(self, messages: list, stream=True):
        """Generator that returns response chunks."""
        for chunk in self.provider.query(messages, stream=stream):
            yield chunk
