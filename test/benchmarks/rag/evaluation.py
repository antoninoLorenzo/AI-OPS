"""
Gets executed by GitHub Actions, loads the synthetic dataset generated in `dataset_generation.ipynb`
into the Qdrant vector database, performs evaluation of the RAG pipeline and outputs the results
as plots in `rag_evaluation_out`; the plots are then added to the relevant EVALUATION.md file.
"""
import json
from pathlib import Path
from tqdm import tqdm
from src.agent.llm import LLM
from src.agent.knowledge import Store, Collection, Document, Topic


def init_knowledge_base(data: dict[str: list[Topic]]) -> Store:
    """Creates a connection to the Vector Database and
    uploads the data used to generate the synthetic dataset.
    :param data: {path to a JSON file : topic list}
    """
    store = Store()
    i = 0
    for p, topics in data.items():
        path = Path(p)
        if not (path.exists() and path.is_file() and path.suffix == '.json'):
            raise ValueError(f'Invalid file {p}. Should be an existing JSON file.')

        # create collection
        collection = Collection(
            i,
            path.name.split('.')[0],
            documents=[],
            topics=topics
        )

        store.create_collection(collection)

        # upload data
        with open(str(path), 'r', encoding='utf-8') as file:
            json_data = json.load(file)

        for doc in tqdm(json_data, total=len(json_data), desc=f'Uploading {path.name}'):
            store.upload(
                Document(name=doc['title'], content=doc['content'], topic=None),
                collection.title
            )

        i += 1

    return store


def evaluate(vdb: Store, synthetic_qa_path: str):
    """Given the Vector Database and the synthetic Q&A dataset
    generated in `dataset_generation.ipynb` runs the evaluation
    process for the RAG pipeline.

    It consists of:

    - Retrieving the contexts and generating the answers for the questions.

    - Evaluating the full contexts-question-answer-ground_truths dataset.
    """
    pass


if __name__ == '__main__':
    knowledge_base: Store = init_knowledge_base({
        '../../../data/json/owasp.json': [Topic.WebPenetrationTesting]
    })
