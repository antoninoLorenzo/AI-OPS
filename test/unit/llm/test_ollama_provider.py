import os
import unittest

from annotated_types import test_cases
from dotenv import load_dotenv
from src.agent.llm import Ollama


class TestOllamaProvider(unittest.TestCase):
    """Tests the Ollama class from `src.agent.llm.llm`

    1. [ ] initialization

        - what happens if model is not supported?
        - what happens if model is not available? (! suppose mistral model is not available)

    2. [ ] `query`: returns a generator for the response tokens (chunks)

        - what happens if message list is empty?
        - what happens if message list is malformed?

            -  case wrong roles
            -  case wrong format (not "role": "", "content": "")
            -  case empty role/content

        - what happens if Ollama is down?

    3. [ ] `tool_query`: returns something that I knew when I wrote the code :|
    """

    def test_init(self):
        CASES = {
            "not_supported_model":
                {
                    "model": "gpt-money",
                    "expected": ValueError
                },
            "not_available_model":
                {
                    # mistral shouldn't be installed on Ollama
                    "model": "mistral",
                    "expected": RuntimeError
                }
        }

        for case_name, case_input in CASES.items():
            model = case_input['model']
            expected = case_input['expected']

            self.assertRaises(expected, Ollama.__init__, model, os.environ['ENDPOINT'])

    def test_query(self):
        CASES = {
            "invalid_type_1":
                {
                    "input": {},
                    "expected": TypeError
                },
            "invalid_type_2":
                {
                    "input": [{}, ""],
                    "expected": TypeError
                },
            "empty_list":
                {
                    "input": [],
                    "expected": ValueError
                },
            "invalid_role":
                {
                    "input": [{"role": "god", "content": "bro"}],
                    "expected": ValueError
                },
            "more_keys":
                {
                    "input": [{"role": "assistant", "content": "bro", "type": "god"}],
                    "expected": ValueError
                },
            "less_keys":
                {
                    "input": [{"role": "assistant"}],
                    "expected": ValueError
                },
            "wrong_keys":
                {
                    "input": [{"type": "god", "text": "bro"}],
                    "expected": ValueError
                },
            "empty_role":
                {
                    "input": [{"role": "", "content": "bro"}],
                    "expected": ValueError
                },
            "empty_content":
                {
                    "input": [{"role": "assistant", "content": ""}],
                    "expected": ValueError
                }
        }

        llm = Ollama(model='gemma2:9b', client_url=os.environ['ENDPOINT'])
        for case_name, case_input in CASES.items():
            test_input = case_input['input']
            expected = case_input['expected']
            print(f'Running case {case_name}\n\t- Input: {test_input}\n\t- Expected: {expected}')

            self.assertRaises(expected, llm.query, test_input)


if __name__ == '__main__':
    load_dotenv()
    if os.environ.get('ENDPOINT') is None:
        print("Please add ENDPOINT environment variable with Ollama endpoint")
    unittest.main()
