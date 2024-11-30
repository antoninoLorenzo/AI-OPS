"""RAG Vector Database interface"""
import json
from pathlib import Path
from typing import Dict, Optional

import httpx
import ollama
import spacy
import qdrant_client.http.exceptions
from qdrant_client import QdrantClient, models
from qdrant_client.http.exceptions import UnexpectedResponse

from src.core.llm.llm import ProviderError
from src.core.knowledge.collections import Collection, Document, Topic


nlp = spacy.load("en_core_web_md")


class Store:
    """Act as interface for Qdrant database.
    Manages Collections and implements the Upload/Retrieve operations."""

    def __init__(
        self,
        base_path: str,
        embedding_url: str = 'http://localhost:11434',
        embedding_model: str = 'nomic-embed-text',
        url: str = 'http://localhost:6333',
        in_memory: bool = False,
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
        """
        self.in_memory = in_memory

        if in_memory:
            self._connection = QdrantClient(':memory:')
            self._collections: Dict[str: Collection] = {}
        else:
            self._connection = QdrantClient(url)
            self._metadata: Path = Path(base_path)
            if not self._metadata.exists():
                self._metadata.mkdir(parents=True, exist_ok=True)

            try:
                available = self.get_available_collections()
            except qdrant_client.http.exceptions.ResponseHandlingException as err:
                raise RuntimeError("Can't get Qdrant collections") from err

            if available:
                coll = dict(available)
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
        except (httpx.ConnectError, ollama._types.ResponseError) as err:
            raise ProviderError("Can't load embedding model") from err

    def create_collection(
        self,
        collection: Collection,
        progress_bar: bool = False
    ):
        """Creates a new Qdrant collection, uploads the collection documents
        using `upload` and creates a metadata file for collection."""
        if collection.title in self.collections:
            return None

        try:
            self._connection.create_collection(
                collection_name=collection.title,
                vectors_config=models.VectorParams(
                    size=self._embedding_size,
                    distance=models.Distance.COSINE
                )
            )
        except UnexpectedResponse as err:
            raise RuntimeError("Can't upload collection") from err

        # upload documents (if present)
        self._collections[collection.title] = collection
        for document in collection.documents:
            self.upload(document, collection.title)

        # should do logging
        # print(f'Collection {collection.title}: '
        #       f'initialized with {len(collection.documents)} documents')

        # update metadata in production (i.e persistent qdrant)
        if not self.in_memory:
            self.save_metadata(collection)

    def upload(
        self,
        document: Document,
        collection_name: str
    ):
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
                payload={
                    'text': item['text'],
                    'title': item['title'],
                    'topic': item['topic']
                }
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

    def retrieve_from(
        self,
        query: str,
        collection_name: str,
        limit: int = 3,
        threshold: int = 0.5
    ) -> list[str] | None:
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
        if not query:
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

    def save_metadata(self, collection: Collection):
        """Saves the collection metadata to the Store knowledge path.
        See [Collection.to_json_metadata](./collections.py)"""
        file_name = collection.title \
            if collection.title.endswith('.json') \
            else collection.title + '.json'
        new_file = str(Path(self._metadata / 'knowledge' / file_name))
        collection.to_json_metadata(new_file)

    def get_available_collections(self) -> Optional[dict[str, Collection]]:
        """Query qdrant for available collections in the database, then loads
        the metadata about the collections from USER/.aiops/knowledge."""
        if self.in_memory:
            return None

        # get collection names from qdrant
        available = self._connection.get_collections()
        names = []
        for collection in available.collections:
            names.append(collection.name)
        collections = []

        # get collection metadata from knowledge folder
        for p in Path(self._metadata / 'knowledge').iterdir():
            if not (p.exists() and p.suffix == '.json' and p.name in names):
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

    @staticmethod
    def get_available_datasets() -> list[Collection]:
        """Searches in USER/.aiops/datasets/ directory for available collections"""
        i = 0
        collections = []
        datasets_path = Path(Path.home() / '.aiops' / 'datasets')
        if not datasets_path.exists():
            return []

        for p in datasets_path.iterdir():
            # `i` is not incremented for each directory entry
            if not (p.is_file() and p.suffix == '.json'):
                p.unlink()
                continue

            with open(p, 'r', encoding='utf-8') as fp:
                data = json.load(fp)

            topics = []
            documents = []
            for item in data:
                topic = Topic(item['category'])
                document = Document(
                    name=item['title'],
                    content=item['content'],
                    topic=topic
                )
                topics.append(topic)
                documents.append(document)

            collection = Collection(
                collection_id=i,
                title=p.name,
                documents=documents,
                topics=topics
            )

            collections.append(collection)
            i += 1

        return collections

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


def chunk(document: Document):
    """Return chunks of a Document that will be added to the Vector Database"""
    return chunk_str(document.content)


def chunk_str(document: str):
    """Chunks a text string, the chunking strategy is:
    NLP sentence extraction -> sentence grouping by similarity.
    """
    doc = nlp(document)
    sentences = [
        sent for sent in list(doc.sents)
        if str(sent).strip() not in ['*']
    ]

    similarities = []
    for i in range(1, len(sentences)):
        if not sentences[i - 1].has_vector or not sentences[i].has_vector:
            similarities.append(0.0)
        else:
            sim = sentences[i-1].similarity(sentences[i])
            similarities.append(sim)

    threshold = 0.5
    max_sent = 4
    sentences = [str(sent) for sent in sentences]
    groups = [[sentences[0]]]
    for i in range(1, len(sentences)):
        if len(groups[-1]) > max_sent or similarities[i-1] < threshold:
            groups.append([sentences[i]])
        else:
            groups[-1].append(sentences[i])

    _chunks = [" ".join(g) for g in groups]
    return [_ch for _ch in _chunks if len(_ch) > 100]
