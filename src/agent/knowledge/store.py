"""RAG Vector Database interface"""
import json
from pathlib import Path
from typing import Dict

import httpx
import ollama
import qdrant_client.http.exceptions
from qdrant_client import QdrantClient, models
from qdrant_client.http.exceptions import UnexpectedResponse

from src.agent.llm.llm import ProviderError
from src.agent.knowledge.collections import Collection, Document, Topic
from src.agent.knowledge.nlp import chunk
from src.agent.knowledge.routing import Router
from src.utils.deprecated import deprecated


class Store:
    """Act as interface for Qdrant database.
    Manages Collections and implements the Upload/Retrieve operations."""

    def __init__(self,
                 embedding_url: str = 'http://localhost:11434',
                 embedding_model: str = 'nomic-embed-text',
                 url: str = 'http://localhost:6333',
                 in_memory: bool = False,
                 router: Router = None
                 ):
        """
        :param embedding_url:
            The url of the Ollama server.
        :param embedding_model:
            The embedding model that will be used to embed the documents.
            Ollama embedding models are:

            - nomic-embed-text (Default)
            - mxbai-embed-large
            - all-minilm
        :param url:
            Url must be provided to specify where is deployed Qdrant.
            Note: it won't be used if `in_memory` is set to True.
        :param in_memory:
            Specifies whether the Qdrant database is loaded in memory
            or it is deployed on a specific endpoint.
        :param router: @deprecated
        """
        self._in_memory = in_memory

        if in_memory:
            self._connection = QdrantClient(':memory:')
            self._collections: Dict[str: Collection] = {}
        else:
            self._connection = QdrantClient(url)
            self._metadata: Path = Path(Path.home() / '.aiops' / 'knowledge')
            if not self._metadata.exists():
                self._metadata.mkdir(parents=True, exist_ok=True)

            try:
                available = self.get_available_collections()
            except qdrant_client.http.exceptions.ResponseHandlingException as err:
                raise RuntimeError(f"Error: {err}")

            if available:
                coll = {name: collection for name, collection in available}
            else:
                coll = {}
            self._collections: Dict[str: Collection] = coll

        self._encoder = ollama.Client(host=embedding_url).embeddings
        self._embedding_model: str = embedding_model

        # noinspection PyProtectedMember
        try:
            self._embedding_size: int = len(
                self._encoder(
                    self._embedding_model,
                    prompt='init'
                )['embedding']
            )
            self._query_router: Router | None = router
        except (httpx.ConnectError, ollama._types.ResponseError) as err:
            raise ProviderError(f"Can't load embedding model: {err}")

    def create_collection(self, collection: Collection):
        """Creates a new Qdrant collection, uploads the collection documents
        using `upload` and creates a metadata file for collection."""
        if collection.title in self.collections:
            return None

        try:
            done = self._connection.create_collection(
                collection_name=collection.title,
                vectors_config=models.VectorParams(
                    size=self._embedding_size,
                    distance=models.Distance.COSINE
                )
            )
        except UnexpectedResponse as err:
            raise RuntimeError(f"Can't upload collection: {err}")

        if done:
            self._collections[collection.title] = collection

        # add documents if already added to Collection
        if len(collection.documents) > 0:
            for document in collection.documents:
                self.upload(document, collection.title)
        print(f'Collection {collection.title}: '
              f'initialized with {len(collection.documents)} documents')

        # update metadata in production
        # TODO: refactor
        if not self._in_memory:
            file_name = collection.title if collection.title.endswith('.json') else collection.title + '.json'
            new_file = str(Path(self._metadata / file_name))

            docs = []
            if len(collection.documents) > 0:
                for document in collection.documents:
                    docs.append({
                        'name': document.name,
                        'content': '',  # document.content,
                        'topic': document.topic.name
                    })

            collection_metadata = {
                'id': collection.collection_id,
                'title': collection.title,
                'documents': docs,
                'topics': [topic.name for topic in collection.topics]
            }

            with open(new_file, 'w+', encoding='utf-8') as fp:
                json.dump(collection_metadata, fp)

            print(f'Collection {collection.title}: saved to {new_file}')

    def upload(self, document: Document, collection_name: str):
        """Performs chunking and embedding of a document
        and uploads it to the specified collection"""
        if not isinstance(collection_name, str):
            raise TypeError(f'Expected str for collection_name, found {type(collection_name)}')
        if collection_name not in self._collections:
            raise ValueError('Collection does not exist')

        # create the Qdrant data points
        doc_chunks = chunk(document)
        emb_chunks = [{
            'title': document.name,
            'topic': str(document.topic),
            'text': ch,
            'embedding': self._encoder(self._embedding_model, ch)['embedding']
        } for ch in doc_chunks]
        current_len = self._collections[collection_name].size

        points = [
            models.PointStruct(
                id=current_len + i,
                vector=item['embedding'],
                payload={'text': item['text'], 'title': item['title'], 'topic': item['topic']}
            )
            for i, item in enumerate(emb_chunks)
        ]

        # upload Points to Qdrant and update Collection metadata
        self._connection.upload_points(
            collection_name=collection_name,
            points=points
        )

        # self._collections[collection_name].documents.append(document)
        self._collections[collection_name].size = current_len + len(emb_chunks)

    @deprecated(reason="Query Routing is handled by LLM tool calling.")
    def retrieve(self, query: str, limit: int = 3):
        """Performs Query Routing and Retrieval of chunks"""
        if not self._query_router:
            raise RuntimeError('retrieve can be called only with a query router')
        collection_name = self._query_router.find_route(
            user_query=query,
            collections=self._collections
        )
        return self.retrieve_from(query, collection_name, limit)

    def retrieve_from(self, query: str, collection_name: str,
                      limit: int = 3,
                      threshold: int = 0.5) -> list[str] | None:
        """Performs retrieval of chunks from the vector database.
        :param query:
            A natural language query used to search in the vector database.
        :param collection_name:
            The name of the collection where the search happens; the collection
            must exist inside the vector database.
        :param limit:
            Number of maximum results returned by the search.
        :param threshold:
            Minimum similarity score that must be satisfied by the search
            results.
        :return: list of chunks or None
        """
        if not len(query):
            raise ValueError('Query cannot be empty')
        if collection_name not in self._collections.keys():
            raise ValueError(f'Collection {collection_name} does not exist')

        hits = self._connection.search(
            collection_name=collection_name,
            query_vector=self._encoder(self._embedding_model, query)['embedding'],
            limit=limit,
            score_threshold=threshold
        )
        results = [points.payload['text'] for points in hits]
        return results if results else None

    def get_available_collections(self):
        """Makes a query to Qdrant and uses collections metadata to get
        existing collections."""
        if self._in_memory:
            return None

        available = self._connection.get_collections()
        names = []
        for collection in available.collections:
            names.append(collection.name)

        collections = []
        for p in self._metadata.iterdir():
            if not (p.exists() and p.suffix == '.json' and p.name in names):
                p.unlink()
                continue

            with open(str(p), 'r', encoding='utf-8') as fp:
                data = json.load(fp)

                docs = []
                for doc in data['documents']:
                    docs.append(Document(
                        name=doc['name'],
                        content=doc['content'],
                        topic=Topic(doc['topic'])
                    ))

                collections.append(Collection(
                    collection_id=data['id'],
                    title=data['title'],
                    documents=docs,
                    topics=[Topic(topic) for topic in data['topics']]
                ))

        return zip(names, collections)

    @property
    def collections(self):
        """All stored collections
        :return dict str: Collection
        """
        return self._collections

    def get_collection(self, name):
        """Get a collection by name"""
        if name not in self.collections:
            return None
        return self._collections[name]

