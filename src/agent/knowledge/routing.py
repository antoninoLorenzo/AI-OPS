"""Implementation of Query Routing mechanism to choose between Collections
"""
import json
from abc import ABC, abstractmethod

from src.agent.knowledge.nlp import extract_keywords, similarity
from src.agent.llm import LLM
from src.agent.prompts import PROMPTS


class Router(ABC):
    """Interface for all routing mechanisms"""

    @abstractmethod
    def find_route(self, user_query: str, collections) -> str:
        """Given an input question and the vector database it returns
        the collection that most likely contains the needed context"""
        raise NotImplementedError()


class SimilarityRouter(Router):
    """Uses NLP techniques to find a candidate collection for a given query"""

    def find_route(self, user_query: str, collections) -> str:
        print(f'Collections: {collections}')
        keywords = extract_keywords(user_query)
        points = {}
        for _, collection in collections.items():
            doc_names = collection.document_names()

            similarities = []
            threshold = 0.7
            for key in keywords:
                for doc_name in doc_names:
                    if key.strip().lower() == doc_name.strip().lower():
                        sim = 1
                    else:
                        sim = similarity(key, doc_name)

                    similarities.append({
                        'document': doc_name,
                        'keyword': key,
                        'similarity': sim
                    })

            similarities = sorted(
                similarities,
                key=lambda k: k['similarity'],
                reverse=True
            )
            # add documents with high similarity to filter

            similarities = [sim for sim in similarities if sim['similarity'] > threshold]
            points[collection.title] = len(similarities)

        return max(points, key=lambda k: points[k])


class LLMRouter(Router):
    """Uses a Large Language Model to find candidate collection for given query.
    Using a local model is not the best choice for performance, HuggingFace
    Inference API could be used in future"""

    def __init__(self, model: str = 'gemma:2b'):
        self.llm = LLM(model)
        self.system_prompt = PROMPTS[model]['routing']['system']
        self.user_prompt = PROMPTS[model]['routing']['user']

    def find_route(self, user_query: str, collections, verbose=False) -> str:
        collection_string = ''
        for _, collection in collections.items():
            collection_string += str(collection)

        prompt = self.user_prompt.format(
            user_query=user_query,
            collections=collection_string
        )
        messages = [
            {'role': 'system', 'content': self.system_prompt},
            {'role': 'user', 'content': prompt}
        ]

        if verbose:
            response = self.llm.query(messages=messages, stream=True)
            text = ''
            for chunk in response:
                print(chunk['message']['content'], end='')
                text += chunk['message']['content']
            print()
            output = json.loads(text)
            return output['collection_name']

        response = self.llm.query(messages, stream=False)
        output = json.loads(response['message']['content'])
        return output['collection_name']
