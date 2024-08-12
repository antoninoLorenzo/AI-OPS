import os
import sys
import unittest

from dotenv import load_dotenv
from src.agent.llm import Ollama, ProviderError


class TestOllamaProvider(unittest.TestCase):
    """Tests the Ollama class from `src.agent.llm.llm`

    1. [x] initialization

        - what happens if model is not supported?
        - what happens if model is not available? (! suppose gemma:7b model is not available)

    2. [ ] `verify_messages_format`: verify that the message format is valid

        - what happens if message list is empty?
        - what happens if message list is malformed?

            -  case wrong roles
            -  case wrong format (not "role": "", "content": "")
            -  case empty role/content

    3. [x] `query`: returns a generator for the response tokens (chunks)

        - what happens if Ollama is down?

    3. [ ] `tool_query`: returns dictionary if llm invoked tools, otherwise None

        - what happens if messages are wrong type/format?
        - what happens if specified model do not support tool calling?
        - what happens if LLM do not invoke any tools?
    """

    @classmethod
    def setUpClass(cls):
        load_dotenv()
        endpoint = os.environ.get('ENDPOINT')
        if not endpoint:
            print("\nPlease add ENDPOINT environment variable with Ollama endpoint")
            sys.exit(-1)

    @staticmethod
    def llm_query(llm, messages):
        for _ in llm.query(messages):
            pass

    def test_init(self):
        print()
        CASES = {
            "not_supported_model":
                {
                    "model": "gpt-money",
                    "expected": ValueError
                },
            "not_available_model":
                {
                    # gemma:7b shouldn't be installed on Ollama
                    "model": "gemma:7b",
                    "expected": RuntimeError
                }
        }

        for case_name, case_input in CASES.items():
            model = case_input['model']
            expected = case_input['expected']
            print(f'Running case {case_name}\n\t- Input: {model}\n\t- Expected: {expected}')

            try:
                _ = Ollama(model, expected)
                self.fail(f'{case_name} should raise {expected}')
            except expected:
                pass

    def test_validate_message(self):
        print()
        CASES = {
            "invalid_type_1":
                {
                    "input":
                        {
                            "messages": {},
                        },
                    "expected": TypeError
                },
            "invalid_type_2":
                {
                    "input":
                        {
                            "messages": [{}, ""],
                        },
                    "expected": TypeError
                },
            "empty_list":
                {
                    "input":
                        {
                            "messages": [],
                        },
                    "expected": TypeError
                },
            "invalid_role":
                {
                    "input":
                        {
                            "messages": [{"role": "god", "content": "bro"}],
                        },
                    "expected": ValueError
                },
            "more_keys":
                {
                    "input":
                        {
                            "messages": [{"role": "assistant", "content": "bro", "type": "god"}],
                        },
                    "expected": ValueError
                },
            "less_keys":
                {
                    "input":
                        {
                            "messages": [{"role": "assistant"}],

                        },
                    "expected": ValueError
                },
            "wrong_keys":
                {
                    "input":
                        {
                            "messages": [{"type": "god", "text": "bro"}],
                        },
                    "expected": ValueError
                },
            "empty_role":
                {
                    "input":
                        {
                            "messages": [{"role": "", "content": "bro"}],
                        },
                    "expected": ValueError
                },
            "empty_content":
                {
                    "input":
                        {
                            "messages": [{"role": "assistant", "content": ""}],

                        },
                    "expected": ValueError
                },
        }

        # noinspection DuplicatedCode
        for case_name, case_input in CASES.items():
            test_input = case_input['input']
            expected = case_input['expected']
            print(f'Running case {case_name}\n\t- Input: {test_input}\n\t- Expected: {expected}')

            messages = test_input['messages']
            self.assertRaises(expected, Ollama.verify_messages_format, messages)

    def test_query(self):
        print()
        CASES = {
            "ollama_down":
                {
                    "input":
                        {
                            "messages": [{"role": "assistant", "content": "Hi"}],
                            "endpoint": "http://ollama_is_down.lol"
                        },
                    "expected": ProviderError
                }
        }

        # noinspection DuplicatedCode
        for case_name, case_input in CASES.items():
            test_input = case_input['input']
            expected = case_input['expected']
            print(f'Running case {case_name}\n\t- Input: {test_input}\n\t- Expected: {expected}')

            messages = test_input['messages']
            endpoint = test_input['endpoint'] if test_input['endpoint'] else \
                os.environ['ENDPOINT']

            test_llm = Ollama(
                model='gemma2:9b',
                client_url=endpoint
            )
            self.assertRaises(expected, self.llm_query, test_llm, messages)

    @unittest.skip
    def test_tool_call(self):
        print()
        CASES = {
            "unsupported_model":
                {
                    "input": {"model": "gemma2:9b"},
                    "expected": NotImplementedError
                },
            "no_tools_called":
                {
                    "input": {"model": "mistral"},
                    "expected": None
                }
        }

        for case_name, case_input in CASES.items():
            test_input = case_input['input']
            expected = case_input['expected']

            llm = Ollama(
                model=test_input['model'],
                client_url=os.environ['ENDPOINT']
            )

            if issubclass(expected, BaseException):
                pass
            else:
                pass


if __name__ == '__main__':
    unittest.main()
