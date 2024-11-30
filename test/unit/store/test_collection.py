import os
import json
import unittest
from pathlib import Path

from src.core.knowledge.collections import Collection


class TestCollection(unittest.TestCase):
    CASES_PATH = Path(Path(__file__).parent / 'collection_schemas')

    @classmethod
    def setUpClass(cls):
        print('\n\n# test_collection.py\n')
        print('## Setup Resources')
        CASES = {
            "not_json_file":
                {
                    "path": "./file.txt",
                    "content": "Hello World"
                },
            "wrong_schema":
                {
                    "path": "./file.json",
                    "content": '{"title": "Wrong", "content": "Hello World", "category": "Wrong"}'
                }
        }

        cls.CASES_PATH.mkdir(parents=True, exist_ok=True)
        for name, info in CASES.items():
            path = str(cls.CASES_PATH / info['path'])
            with open(path, 'w+') as fp:
                if info['path'].endswith('.json'):
                    json.dump(info['content'], fp)
                else:
                    fp.write(info['content'])

    @classmethod
    def tearDownClass(cls):
        print('\n\n## Clean Resources')
        try:
            for path in cls.CASES_PATH.iterdir():
                os.remove(str(path))
            os.rmdir(str(cls.CASES_PATH))
        except OSError as error:
            print(f"Failed to remove test cases resources inside {cls.CASES_PATH}.")
            print(error)

    def test_from_json(self):
        print()
        CASES = {
            "path_not_exists":
                {
                    "input": {"path": "./ne"},
                    "expected": ValueError
                },
            "not_json_file":
                {
                    "input": {"path": "./file.txt"},
                    "expected": ValueError
                },
            "wrong_schema":
                {
                    "input": {"path": ".//file.json"},
                    "expected": ValueError
                }
        }

        for case_name, case_input in CASES.items():
            path = self.CASES_PATH / case_input['input']['path']
            expected = case_input["expected"]
            print(f'Running case {case_name}\n\t- path: {path}\n\t- expected: {expected}')
            self.assertRaises(
                expected,
                Collection.from_json,
                str(path)
            )


if __name__ == "__main__":
    unittest.main()
