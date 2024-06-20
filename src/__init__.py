import json
from pathlib import Path

from src.agent.knowledge import Store
from src.agent.knowledge import Collection, Document, Topic


def upload_knowledge(path: str, vdb: Store):
    """Used to initialize and keep updated the Knowledge Base.
    Already existing Collections will not be overwritten.
    :param path: where the JSON datasets are located.
    :param vdb: the reference to the Knowledge Base"""
    base_path = Path(path)

    for i, p in enumerate(base_path.iterdir()):
        if not (p.is_file() and p.suffix == '.json'):
            continue

        if p.name in ['hack_tricks.json', 'null_byte.json']:
            continue

        with open(str(p), 'r', encoding='utf-8') as file:
            data = json.load(file)

            documents = []
            topics = set()
            for item in data:
                topic = Topic(item['category'])
                topics.add(topic)

                document = Document(
                    name=item['title'],
                    content=item['content'],
                    topic=topic
                )
                documents.append(document)

            collection = Collection(
                collection_id=i,
                title=p.name,
                documents=documents,
                topics=list(topics)
            )
            vdb.create_collection(collection)
