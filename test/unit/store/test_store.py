import os
import sys
import unittest

from dotenv import load_dotenv

from src.core.llm import ProviderError
from src.core.knowledge import Store, Collection
from src.core.knowledge.collections import Document, Topic


class TestStore(unittest.TestCase):

    DOCUMENT_MOCK = {
        "mock": Document('mock_doc', "Hello World", Topic("nothing")),
        "empty": Document('e_doc', "", Topic("nothing"))
    }

    @classmethod
    def setUpClass(cls):
        print('\n\n# test_store.py\n')
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
                            "ollama_url": "http://localhost:54321",
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

    @unittest.skip
    def test_upload(self):
        store = Store(embedding_url=os.environ.get('ENDPOINT'))

        CASES = {
            "type_collection_name":
                {
                    "input":
                        {
                            "document": self.DOCUMENT_MOCK['mock'],
                            "collection_name": 1
                        },
                    "expected": TypeError
                },
            "empty_collection_name":
                {
                    "input":
                        {
                            "document": self.DOCUMENT_MOCK['mock'],
                            "collection_name": ""
                        },
                    "expected": ValueError
                },
            "not_exists_collection_name":
                {
                    "input":
                        {
                            "document": self.DOCUMENT_MOCK['mock'],
                            "collection_name": "god"
                        },
                    "expected": ValueError
                },
            "empty_document":
                {
                    "input": {
                        "document": self.DOCUMENT_MOCK['empty'],
                        "collection_name": "test"
                    },
                    "expected": ValueError
                },
        }

        try:
            store.create_collection(Collection(2, 'test', [], []))
        except RuntimeError:
            pass

        for case_name, case_input in CASES.items():
            case_document = case_input['input']['document']
            case_c_name = case_input['input']['collection_name']
            expected = case_input['expected']

            print(f'Running case {case_name}\n\t- Input: {case_input["input"]}\n\t- Expected: {expected}')

            self.assertRaises(
                expected,
                store.upload,
                case_document,
                case_c_name
            )

    def test_retrieve_from(self):
        store = Store(embedding_url=os.environ.get('ENDPOINT'))

        CASES = {
            "na_query":
                {
                    "input":
                        {
                            "query": "",
                            "collection_name": "test",
                            "limit": 3,
                            "threshold": 0.5
                        },
                    "expected": ValueError
                },
            "ne_collection_name":
                {
                    "input":
                        {
                            "query": "Hello World",
                            "collection_name": "god",
                            "limit": 3,
                            "threshold": 0.5
                        },
                    "expected": ValueError
                },
            "oob_limit":
                {
                    "input":
                        {
                            "query": "Hello World",
                            "collection_name": "test",
                            "limit": 0,
                            "threshold": 0.5
                        },
                    "expected": ValueError
                },
            "lower_oob_threshold":
                {
                    "input":
                        {
                            "query": "Hello World",
                            "collection_name": "test",
                            "limit": 0,
                            "threshold": 0
                        },
                    "expected": ValueError
                },
            "higher_oob_threshold":
                {
                    "input":
                        {
                            "query": "Hello World",
                            "collection_name": "test",
                            "limit": 0,
                            "threshold": 0.99
                        },
                    "expected": ValueError
                },
        }

        try:
            store.create_collection(Collection(2, 'test', [], []))
        except RuntimeError:
            pass

        for case_name, case_input in CASES.items():
            case_query = case_input['input']['query']
            case_c_name = case_input['input']['collection_name']
            case_limit = case_input['input']['limit']
            case_threshold = case_input['input']['threshold']
            expected = case_input['expected']

            print(f'Running case {case_name}\n\t- Input: {case_input["input"]}\n\t- Expected: {expected}')

            self.assertRaises(
                expected,
                store.retrieve_from,
                case_query,
                case_c_name,
                case_limit,
                case_threshold
            )


if __name__ == '__main__':
    unittest.main()
