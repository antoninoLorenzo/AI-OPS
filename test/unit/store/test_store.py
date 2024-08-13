import os
import sys
import unittest

from dotenv import load_dotenv

from src.agent.llm.llm import ProviderError
from src.agent.knowledge.store import Store
from src.agent.knowledge.collections import Collection, Document, Topic


class TestStore(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        load_dotenv()
        endpoint = os.environ.get('ENDPOINT')
        if not endpoint:
            print("\nPlease add ENDPOINT environment variable with Ollama endpoint")
            sys.exit(-1)

    @unittest.skip
    def test_initialization(self):
        CASES = {
            "qdrant_unavailable":
                {
                    "input":
                        {
                            "qdrant_url": "http://localhost:12345",
                            "ollama_url": os.environ['ENDPOINT'],
                            "model": "nomic-embed-text"
                        },
                    "expected": RuntimeError
                },
            "ollama_unavailable":
                {
                    "input":
                        {
                            "qdrant_url": "http://localhost:6333",
                            "ollama_url": "http://localhost:12345",
                            "model": "nomic-embed-text"
                        },
                    "expected": ProviderError
                },
            "model_unavailable":
                {
                    "input":
                        {
                            "qdrant_url": "http://localhost:6333",
                            "ollama_url": os.environ['ENDPOINT'],
                            "model": "all-minilm"  # ! suppose it isn't available
                        },
                    "expected": ProviderError
                },
        }

        for case_name, case_input in CASES.items():
            qdrant_url = case_input['input']['qdrant_url']
            ollama_url = case_input['input']['ollama_url']
            model = case_input['input']['model']
            expected = case_input['expected']
            print(f'Running case {case_name}\n\t- Input: {case_input["input"]}\n\t- Expected: {expected}')

            try:
                _ = Store(url=qdrant_url, embedding_url=ollama_url, embedding_model=model)
                self.fail(f"{case_name} should raise {expected}")
            except expected:
                pass

    def test_upload(self):
        # TODO: make collection mocks
        CASES = {
            "type_collection_name":
                {
                    "input":
                        {
                            "collection": None,
                            "collection_name": 1
                        },
                    "expected": TypeError
                },
            "empty_collection_name":
                {
                    "input":
                        {
                            "collection": None,
                            "collection_name": ""
                        },
                    "expected": ValueError
                },
            "not_exists_collection_name":
                {
                    "input":
                        {
                            "collection": None,
                            "collection_name": "god"
                        },
                    "expected": ValueError
                },
            "empty_collection":
                {
                    "input": {
                        "collection": None,
                        "collection_name": "test"
                    },
                    "expected": ValueError
                }
        }

        for case_name, case_input in CASES.items():
            pass


if __name__ == '__main__':
    unittest.main()
