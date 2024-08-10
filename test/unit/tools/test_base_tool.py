import os
import json
import unittest
from pathlib import Path

from src.agent.tools.base import Tool


class TestBaseTool(unittest.TestCase):
    """Tests the Tool class in `src.agent.tools.base`.

    The implemented tests must answer the following questions:
    1. [x] `load_tool`: create Tool object from json file

        - what happens if json schema is wrong?
        - what happens if the content of json fields is empty?
        - what happens if the provided path doesn't exist?

    2. [ ] `run`: executes a command

        - what happens if tool execution fails?
    """
    SCHEMA_PATH = Path(Path(__file__).parent / 'base_tool_schemas')

    @classmethod
    def setUpClass(cls):
        print('\n\n# Setup Resources')
        WRONG_SCHEMAS = {
            "wrong_type": "",
            "empty_schema": {},
            "missing_keys": {"name": "test"},
            "more_keys": {"name": "test", "tool_description": "tool", "args_description": "", "sum_else": ""},
            "wrong_schema": {"1": 1, "2": 2, "3": 3},
            "empty_field": {"name": "test", "tool_description": "tool", "args_description": ""},
            "nested_schema": [{"name": "test"}],
        }

        print(f'--- Creating schema DIR {cls.SCHEMA_PATH}')
        cls.SCHEMA_PATH.mkdir(parents=True, exist_ok=True)
        for name, schema in WRONG_SCHEMAS.items():
            print(f'--- Creating schema JSON: {name}')
            path = str(Path(cls.SCHEMA_PATH / name))
            with open(f'{path}.json', 'w+') as fp:
                json.dump(schema, fp)

    @classmethod
    def tearDownClass(cls):
        print('\n\n# Clean Resources')
        try:
            for path in cls.SCHEMA_PATH.iterdir():
                os.remove(str(path))
            os.rmdir(str(cls.SCHEMA_PATH))

            print(f"Directory {cls.SCHEMA_PATH} has been removed successfully")
        except OSError as error:
            print(error)
            print(f"Directory {cls.SCHEMA_PATH} can not be removed")

    def test_load_tool(self):
        print()
        EXPECTED = {
            "wrong_type": TypeError,
            "empty_schema": ValueError,
            "missing_keys": ValueError,
            "more_keys": ValueError,
            "wrong_schema": ValueError,
            "empty_field": ValueError,
            "nested_schema": TypeError,
        }

        for path in Path(f'./{self.SCHEMA_PATH}').iterdir():
            expected = EXPECTED[path.name.split('.')[0]]
            print(f'Loading {path.name}; expected: {str(expected)}')
            self.assertRaises(expected, Tool.load_tool, str(path))


if __name__ == "__main__":
    unittest.main()
