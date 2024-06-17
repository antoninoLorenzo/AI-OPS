from typing import Dict

import ollama
from qdrant_client import QdrantClient, models

from src.agent.knowledge.chunker import chunk
from src.agent.knowledge.collections import Document, Collection


class Store:
    """Act as interface for Qdrant database"""

    def __init__(self):
        self._connection = QdrantClient(":memory:")
        self._collections: Dict[str: Collection] = {}

        self._encoder = ollama.embeddings
        self._embedding_model: str = 'nomic-embed-text'
        self._embedding_size: int = len(
            self._encoder(
                self._embedding_model,
                prompt='init'
            )['embedding']
        )

    def create_collection(self, collection: Collection):
        """Creates a new Qdrant collection"""
        done = self._connection.create_collection(
            collection_name=collection.title,
            vectors_config=models.VectorParams(
                size=self._embedding_size,
                distance=models.Distance.COSINE
            )
        )
        if done:
            self._collections[collection.title] = collection

        # add documents if already added to Collection
        if len(collection.documents) > 0:
            for document in collection.documents:
                self.upload(document, collection.title)

    def upload(self, document: Document, collection_name: str):
        """Performs chunking and embedding of a document and uploads it to the specified collection"""
        if collection_name not in self._collections:
            raise ValueError('Collection does not exist')

        # create the Qdrant data points
        doc_chunks = chunk(document)
        emb_chunks = [{
            'title': document.name,
            # 'topic': str(document.topic)
            'text': ch,
            'embedding': self._encoder(self._embedding_model, ch)
        } for ch in doc_chunks]
        current_len = self._collections[collection_name].size

        points = [
            models.PointStruct(
                id=current_len + i,
                vector=item['embedding']['embedding'],
                payload={'text': item['text'], 'title': item['title']}
            )
            for i, item in enumerate(emb_chunks)
        ]

        # upload Points to Qdrant and update Collection metadata
        self._connection.upload_points(
            collection_name=collection_name,
            points=points
        )

        self._collections[collection_name].documents.append(document)
        self._collections[collection_name].size = current_len + len(emb_chunks)

    def retrieve(self, query: str, collection_name: str, limit: int = 3):
        """Performs retrieval of chunks from the vector database"""
        if len(query) < 3:
            return None

        hits = self._connection.search(
            collection_name=collection_name,
            query_vector=self._encoder(self._embedding_model, query)['embedding'],
            limit=limit
        )
        return hits

    @property
    def collections(self):
        return self._collections

    def get_collection(self, name):
        if name not in self.collections:
            return None
        return self._collections[name]
