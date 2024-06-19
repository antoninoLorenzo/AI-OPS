"""The metrics used to perform the RAG evaluation"""
import re
import json
import textwrap
from json import JSONDecodeError
from dataclasses import dataclass
from abc import ABC, abstractmethod

import requests
import numpy as np


EVAL_PROMPTS = {
    'mistral': {
        'context_recall': {
            'sys': '',
            'usr': ''
        },
        'context_precision': {
            'sys': '',
            'usr': ''
        }
    }
}


@dataclass
class HuggingFaceLLM:
    """Represents HuggingFace Inference Endpoint, it is used for convenience in performance of evaluation."""
    url: str
    key: str

    def __post_init__(self):
        self.headers = {"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"}

    def __query(self, payload):
        response = requests.post(self.url, headers=self.headers, json={'inputs': payload})
        response.raise_for_status()
        return response.json()

    def query(self, messages: list):
        prompt = '\n'.join([msg['content'] for msg in messages])
        return self.__query(prompt)


@dataclass
class Metric(ABC):
    """Represents a RAG evaluation metric using LLM-as-a-judge paradigm"""
    system_prompt: str
    user_prompt: str
    llm_provider: HuggingFaceLLM

    @abstractmethod
    def compute(self, *args, **kwargs) -> float:
        """Needs to be implemented to evaluate a metric"""
        pass

