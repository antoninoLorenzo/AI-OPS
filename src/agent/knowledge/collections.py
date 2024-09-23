"""RAG related data"""
import json
import os
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Topic:
    """One of the possible Penetration Testing topics, used to choose
    a collection and to filter documents"""
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
    collection_id: int
    title: str
    documents: List[Document]
    topics: List[Topic]
    size: Optional[int] = 0  # points to the number of chunks in a Collection

    @staticmethod
    def from_json(path: str):
        """Create a collection from a JSON file in the following format:
        [
            {
                "title": "collection title",
                "content": "collection content",
                "category": "collection topics" | ["topic1", "topic2"]
            },
            ...,
        ]
        :param path: path to the json file.
        :return: Collection
        """
        # path string validation
        if not path or not isinstance(path, str):
            raise ValueError("Invalid parameter for path.")
        if not os.path.exists(path):
            raise ValueError(f"Path {path} does not exist.")
        if not os.path.isfile(path) or \
                not os.path.basename(path).endswith(".json"):
            raise ValueError(f"Path {path} is not JSON file")

        # load json file
        with open(path, 'r', encoding='utf-8') as fp:
            data = json.load(fp)

        # json scheme validation
        format_err_msg = f"Invalid format for {os.path.basename(path)}. "
        if not isinstance(data, list):
            raise ValueError(format_err_msg + "Not a list.")

        valid_dict = [isinstance(item, dict) for item in data]
        if False in valid_dict:
            raise ValueError(format_err_msg + "Found not dict item.")

        all_keys = [list(item.keys()) for item in data]
        valid_keys = [
            'title' in keys and 'content' in keys and 'category' in keys
            for keys in all_keys
        ]
        if False in valid_keys:
            raise ValueError(format_err_msg + "Not found required keys.")

        documents: list[Document] = []
        all_topics: list[Topic] = []
        for item in data:
            title = item['title']
            content = item['content']
            category = item['category']
            if isinstance(category, list):
                topics = ', '.join(category)
                all_topics.extend([Topic(topic) for topic in category])
            else:
                topics = category
                all_topics.append(Topic(category))

            documents.append(Document(
                name=title,
                content=content,
                topic=topics
            ))

        title = os.path.basename(path).split('.')[0]
        return Collection(
            collection_id=-1,
            title=title,
            documents=documents,
            topics=all_topics,
            size=len(documents)
        )

    def to_json_metadata(self, path: str):
        """Saves the collection to the specified metadata file.
        ex. USER/.aiops/knowledge/collection_name.json
        {
            'id'
            'title'
            'documents': [
                {'name', 'topic'}
                ...
            ]
            'topics': [...]
        }"""
        print(f'Saving to {path}')
        docs = []
        if len(self.documents) > 0:
            for document in self.documents:
                docs.append({
                    'name': document.name,
                    'content': '',  # document.content,
                    'topic': document.topic.name
                })

        collection_metadata = {
            'id': self.collection_id,
            'title': self.title,
            'documents': docs,
            'topics': [topic.name for topic in self.topics]
        }

        with open(path, 'w+', encoding='utf-8') as fp:
            json.dump(collection_metadata, fp)

    def document_names(self) -> list:
        """The document names are used to filter queries to the
        Knowledge Database"""
        return [doc.name for doc in self.documents]

    def __str__(self):
        docs = "| - Documents\n"
        for doc in self.documents:
            docs += f'    | - {doc.name}\n'
        topics = ", ".join([topic.name for topic in self.topics])
        return (f'Title: {self.title} ({self.collection_id})\n'
                f'| - Topics: {topics}\n'
                f'{docs}')


if __name__ == "__main__":
    c = Collection.from_json('../../../data/json/owasp.json')
    print(c)
