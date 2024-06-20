"""Implementation of Query Routing mechanism to choose between Collections
"""
from abc import ABC, abstractmethod
from typing import Dict

from src.agent.llm import LLM
from src.agent.knowledge.nlp import extract_keywords, similarity
from src.agent.knowledge.collections import Collection


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
        for c_name, collection in collections.items():
            doc_names = collection.document_names()

            similarities = []
            threshold = 0.7
            for kw in keywords:
                for doc_name in doc_names:
                    if kw.strip().lower() == doc_name.strip().lower():
                        sim = 1
                    else:
                        sim = similarity(kw, doc_name)

                    similarities.append({
                        'document': doc_name,
                        'keyword': kw,
                        'similarity': sim
                    })

            similarities = sorted(similarities, key=lambda k: k['similarity'], reverse=True)
            # add documents with high similarity to filter

            similarities = [sim for sim in similarities if sim['similarity'] > threshold]
            points[collection.title] = len(similarities)

        return max(points, key=lambda k: points[k])


class LLMRouter(Router):
    def find_route(self, user_query: str, collections) -> str:
        pass

