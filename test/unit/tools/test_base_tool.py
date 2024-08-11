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

    2. [x] `run`: executes a command

        - what happens if invalid input is provided? (not the string command)
        - what happens if command execution fails?
        - what happens if a command never exits its execution?
            > some commands will run for long (ex. nmap, hashcat);
            > inspection should be implemented (...).
    """
    SCHEMA_PATH = Path(Path(__file__).parent / 'base_tool_schemas')
    CMDS_PATH = Path(Path(__file__).parent / 'cmd_cases.json')

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

        CMDS_CASES = {
            "invalid_type": 1,
            "empty_input": "",
            "single_arg": "ls",
            "multi_arg": "ls -la",
            "wrong_arg": "ls --invalid"
        }

        print(f'--- Creating schema DIR {cls.SCHEMA_PATH}')
        cls.SCHEMA_PATH.mkdir(parents=True, exist_ok=True)
        for name, schema in WRONG_SCHEMAS.items():
            # print(f'--- Creating schema JSON: {name}')
            path = str(Path(cls.SCHEMA_PATH / name))
            with open(f'{path}.json', 'w+') as fp:
                json.dump(schema, fp)

        print(f'--- Creating run test cases {cls.CMDS_PATH}')
        with open(cls.CMDS_PATH, 'w+') as fp:
            json.dump(CMDS_CASES, fp)

    @classmethod
    def tearDownClass(cls):
        print('\n\n# Clean Resources')
        try:
            for path in cls.SCHEMA_PATH.iterdir():
                os.remove(str(path))
            os.rmdir(str(cls.SCHEMA_PATH))
            os.remove(str(cls.CMDS_PATH))

            print(f"Setup files removed successfully")
        except OSError as error:
            print(error)
            print(f"Failed to remove one of the following:\n{cls.SCHEMA_PATH}\n{cls.CMDS_PATH}")

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

    def test_run_tool(self):
        print()
        EXPECTED = {
            "invalid_type": TypeError,
            "empty_input": ValueError,
            "single_arg": True,
            "multi_arg": True,
            "wrong_arg": True
        }

        with open(self.CMDS_PATH, 'r') as fp:
            test_case: dict = json.load(fp)
            for case, cmd_input in test_case.items():
                print(f'Executing case {case}: {cmd_input}')
                if EXPECTED[case] is True:
                    self.assertIsNotNone(Tool.run(cmd_input), f"Empty output for {cmd_input}")
                else:
                    self.assertRaises(EXPECTED[case], Tool.run, cmd_input)


if __name__ == "__main__":
    unittest.main()
