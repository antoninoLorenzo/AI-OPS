"""The metrics used to perform the RAG evaluation"""
import re
import json
import textwrap
from json import JSONDecodeError
from dataclasses import dataclass
from abc import ABC, abstractmethod

import requests
import numpy as np

from src.agent.llm import LLM, Ollama


EVAL_PROMPTS = {
    'gemma2:9b': {
        'context_recall': {
            'sys': """
Given a context and an answer, you should analyze the answer. Then ensure the answer information is confirmed by the context information. 
Evaluate the overall accuracy of the answer based on the given context. Use the following categorical scoring system for your classification:
- "great" (1): The answer is highly relevant and clearly supported by the context.
- "good" (0.7): The answer is relevant and somewhat supported by the context.
- "inaccurate" (0.3): The answer is not clearly supported by the context but is not entirely irrelevant.
- "bad" (0): The answer contains information that contradicts the context, indicating a hallucination.

Your output should contain a single categorical score for the overall answer, formatted as a JSON string as follows:
{{"result": "great" | "good" | "inaccurate" | "bad"}}

Evaluation Guidelines:
- Only provide the JSON string in the specified format. Do not include any additional text.
- If the answer mentions that available information wasn't sufficient, your response should be the following: {{"result": "bad"}}
- Ensure your assessment is based on how well the overall answer aligns with the given context.""",
            'usr': """Answer:
{answer}

Context:
{context}

Your output should contain a single categorical score for the overall answer, formatted as a JSON string as follows:
{{"result": "great" | "good" | "inaccurate" | "bad"}}

IMPORTANT:
- Remember to follow the "Evaluation Guidelines"
- Provide only the JSON string, do not provide any explanation."""
        },
        'context_precision': {
            'sys': """
Given a question, answer, and context, evaluate if the context was useful in arriving at the given answer. Use the following categorical scoring system for your classification:
- "great" (1): The context was highly useful and directly supported the answer.
- "good" (0.7): The context was useful and somewhat supported the answer.
- "inaccurate" (0.3): The context was only slightly useful and not directly supporting the answer.
- "bad" (0): The context was not useful or irrelevant in arriving at the answer.

Your output should contain a single categorical score for the overall answer, formatted as a JSON string as follows:
{{"result": "great" | "good" | "inaccurate" | "bad"}}

Evaluation Guidelines:
- Only provide the JSON string in the specified format. Do not include any additional text.
- If the answer does not respond to the question or mentions that available information wasn't sufficient, your response should be the following: {{"result": "not useful"}}
- Ensure your assessment is based on how well the context was useful in arriving at the answer.""",
            'usr': """Question:
{question}

Context:
{context}

Answer:
{answer}

Your output should contain a single categorical score for the overall answer, formatted as a JSON string as follows:
{{"result": "great" | "good" | "inaccurate" | "bad"}}

IMPORTANT:
- Remember to follow the "Evaluation Guidelines"
- Provide only the JSON string, do not provide any explanation."""
        }
    }
}

METRICS_VALUES = {
    'great': 1,
    'good': 0.7,
    'inaccurate': 0.3,
    'bad': 0
}

JSON_PATTERN = r'{"result": \[[^\]]*\]}'


@dataclass
class Metric(ABC):
    """Represents a RAG evaluation metric using LLM-as-a-judge paradigm"""
    system_prompt: str
    user_prompt: str
    llm: LLM

    @abstractmethod
    def compute(self, *args, **kwargs) -> float:
        """Needs to be implemented to evaluate a metric"""
        pass

    @staticmethod
    def extract_response(response):
        """Extracts the json results from response"""
        try:
            # TODO: validate response response type
            label = json.loads(response)['result']
            return METRICS_VALUES[label] if label in METRICS_VALUES else 0
        except JSONDecodeError:
            match = re.search(JSON_PATTERN, response)
            if match:
                return float(json.loads(match.group())['result'])
            else:
                return response


class ContextRecall(Metric):
    """Assesses how much the answer is based on the context"""

    def compute(self, answer: str, context: str):
        """Computes context recall given answer and context"""
        messages = [
            {'role': 'system', 'content': self.system_prompt},
            {'role': 'user', 'content': self.user_prompt.format(answer=answer, context=context)}
        ]

        response = self.llm.query(messages)
        result = ''
        for chunk in response:
            result += chunk
        return self.extract_response(result)


class ContextPrecision(Metric):
    """Assesses how much the context was useful in generating the answer"""

    def compute(self, question: str, answer: str, context: str):
        """Uses question, answer and context"""
        messages = [
            {'role': 'system', 'content': self.system_prompt},
            {'role': 'user', 'content': self.user_prompt.format(question=question, answer=answer, context=context)}
        ]

        response = self.llm.query(messages)
        result = ''
        for chunk in response:
            result += chunk
        return self.extract_response(result)

