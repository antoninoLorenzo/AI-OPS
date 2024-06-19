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
    'mistral:7b': {
        'context_recall': {
            'sys': textwrap.dedent("""
                Given a context, and an answer, analyze each sentence in the answer and classify if the sentence can be attributed to the given context or not. Use only "Yes" (1) or "No" (0) as a binary classification. 
                
                Your output should contain a list of 0 or 1 for each sentence, also it should be a JSON string as follows:
                {{"result": [1, 0, ...]}}
                
                IMPORTANT:
                - Only provide the JSON string in the specified format. Do not include any additional text.
                - If the answer mentions that available information wasn't sufficient, your response should be the following: {{"result": [0]}}
            """),
            'usr': textwrap.dedent("""
                Answer:
                {answer}
                
                Context:
                {context}
                
                Your output should contain a list of 0 or 1 for each sentence, also it should be a JSON string as follows:
                {{"result": [1, 0, ...]}}
                
                IMPORTANT:
                - Only provide the JSON string in the specified format. Do not include any additional text.
                - If the answer mentions that available information wasn't sufficient, your response should be the following: {{"result": [0]}}
            """)
        },
        'context_precision': {
            'sys': textwrap.dedent("""
                Given question, answer and context verify if the context was useful in arriving at the given answer. 
                Use only "Useful" (1) or "Not Useful" (0) as a binary classification. 
                
                Your output should contain a list of 0 or 1 for each sentence, also it should be a JSON string as follows:
                {{"result": [1, 0, ...]}}
                
                IMPORTANT:
                - Only provide the JSON string in the specified format. Do not include explanations or any additional text.
                - If the answer do not provide a response to the question or mentions that available information wasn't sufficient, your response should be the following:  {{"result": [0]}}
            """),
            'usr': textwrap.dedent("""
                Question:
                {question}
                
                Context:
                {context}
                
                Answer:
                {answer}
                
                Your output should contain a list of 0 or 1 for each sentence, also it should be a JSON string as follows:
                {{"result": [1, 0, ...]}}
                
                IMPORTANT:
                - Only provide the JSON string in the specified format. Do not include explanations or any additional text.
                - If the answer do not provide a response to the question or mentions that available information wasn't sufficient, your response should be the following:  {{"result": [0]}}
            """)
        }
    }
}
JSON_PATTERN = r'{"result": \[[^\]]*\]}'


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

    @staticmethod
    def extract_response(response: list):
        """Extracts the json results from a HuggingFace Inference Endpoint response"""
        eval_json = response[0]['generated_text'].split('\n')[-1]

        try:
            return np.mean(json.loads(eval_json)['result'])
        except JSONDecodeError:
            match = re.search(JSON_PATTERN, eval_json)
            if match:
                return np.mean(json.loads(match.group())['result'])
            else:
                return eval_json


class ContextRecall(Metric):
    """Assesses how much the answer is based on the context"""

    def compute(self, answer: str, context: str):
        """Computes context recall given answer and context"""
        messages = [
            {'role': 'system', 'content': self.system_prompt},
            {'role': 'user', 'content': self.user_prompt.format(answer=answer, context=context)}
        ]

        result = self.llm_provider.query(messages)
        return self.extract_response(result)


class ContextPrecision(Metric):
    """Assesses how much the context was useful in generating the answer"""

    def compute(self, question: str, answer: str, context: str):
        """Uses question, answer and context"""
        messages = [
            {'role': 'system', 'content': self.system_prompt},
            {'role': 'user', 'content': self.user_prompt.format(question=question, answer=answer, context=context)}
        ]

        result = self.llm_provider.query(messages)
        return self.extract_response(result)

