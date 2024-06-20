"""RAG related data"""
from dataclasses import dataclass
from enum import StrEnum
from typing import List, Optional


@dataclass
class Topic:
    """One of the possible Penetration Testing topics, used to choose a collection
    and to filter documents"""
    name: str

    def __str__(self):
        return self.name

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        if isinstance(other, Topic):
            return self.name == other.name
        return False

    def __ne__(self, other):
        return not self.__eq__(other)


@dataclass
class Document:
    """Represents a processed data source such as HTML or PDF documents; it will
    be chunked and added to a Vector Database"""
    name: str
    content: str
    topic: Optional[Topic]

    def __str__(self):
        return f'{self.name} [{str(self.topic)}]\n{self.content}'


@dataclass
class Collection:
    """Represents a Qdrant collection"""
    id: int
    title: str
    documents: List[Document]
    topics: List[Topic]
    size: Optional[int] = 0

    def __str__(self):
        docs = "| - Documents\n"
        for doc in self.documents:
            docs += f'    | - {doc.name}\n'
        return f'Title: {self.title} ({self.id})\n| - Topics: {", ".join(self.topics)}\n{docs}'

