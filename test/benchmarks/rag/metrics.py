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
        },
        'context_relevancy': {
            'sys': """Given a question and multiple chunks of context, you should analyze each chunk of context to determine its relevancy in answering the question. Use the following categorical scoring system for your classification:
- "great" (1): The context chunk is fundamental and essential to provide an answer.
- "good" (0.7): The context chunk is useful and relevant to the answer, but not fundamental.
- "inaccurate" (0.3): The context chunk is on the same topic as the answer but isn't useful in providing a response.
- "bad" (0): The context chunk is on a different topic and not relevant to the question.

Your output should contain a list of categorical scores for each context chunk, formatted as a JSON string as follows:
{{"result": ["great" | "good" | "inaccurate" | "bad", ...]}}

Evaluation Guidelines:
- Only provide the JSON string in the specified format. Do not include any additional text.
- Ensure your assessment is based on how well each context chunk aligns with the given question and supports the answer.
- If a context chunk lacks sufficient information to be relevant to the question, your response should be "bad".
- Ensure your evaluation reflects the necessity and relevancy of each context chunk in addressing the query.""",
            'usr': """Question:
{question}

Contexts:
{context}

Your output should contain a list of categorical scores for each context chunk, formatted as a JSON string as follows:
{{"result": ["great" | "good" | "inaccurate" | "bad", ...]}}

IMPORTANT:
- Remember to follow the "Evaluation Guidelines"
- Provide only the JSON string, do not provide any explanation.

"""
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

    def query(self, sys_prompt: str, usr_prompt: str) -> str:
        """"""
        messages = [
            {'role': 'system', 'content': sys_prompt},
            {'role': 'user', 'content': usr_prompt}
        ]
        response = self.llm.query(messages)
        result = ''
        for chunk in response:
            result += chunk
        return self.extract_response(result)

    @staticmethod
    def extract_response(response):
        """Extracts the json results from response"""
        try:
            result = json.loads(response)['result']
            if result is list:
                # list of labels (ex. context relevancy)
                values = []
                for label in result:
                    values.append(METRICS_VALUES[label] if label in METRICS_VALUES else 0)
                return np.mean(values)

            # single label (ex. context precision)
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

    def compute(self, data: dict):
        """Computes context recall given answer and context"""
        return self.query(
            self.system_prompt,
            self.user_prompt.format(answer=data['answer'], context=data['context'])
        )


class ContextPrecision(Metric):
    """Assesses how much the context was useful in generating the answer"""

    def compute(self, data: dict):
        """Uses question, answer and context"""
        return self.query(
            self.system_prompt,
            self.user_prompt.format(question=data['question'], answer=data['answer'], context=data['context'])
        )


class ContextRelevancy(Metric):
    """Assesses how much relevant is the retrieved context to the query"""

    def compute(self, data: dict):
        return self.query(
            self.system_prompt,
            self.user_prompt.format(question=data['question'], context=data['context'])
        )
