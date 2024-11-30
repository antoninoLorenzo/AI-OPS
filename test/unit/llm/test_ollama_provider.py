import os
import sys
import unittest

from dotenv import load_dotenv
from tool_parse import ToolRegistry
from src.core import Ollama, ProviderError


class TestOllamaProvider(unittest.TestCase):
    """Tests the Ollama class from `src.agent.llm.llm`

    1. [x] initialization

        - what happens if model is not supported?
        - what happens if model is not available? (! suppose gemma:7b model is not available)

    2. [x] `verify_messages_format`: verify that the message format is valid

        - what happens if message list is empty?
        - what happens if message list is malformed?

            -  case wrong roles
            -  case wrong format (not "role": "", "content": "")
            -  case empty role/content

    3. [x] `query`: returns a generator for the response tokens (chunks)

        - what happens if Ollama is down?

    3. [x] `tool_query`: returns dictionary if llm invoked tools, otherwise None

        - what happens if specified model do not support tool calling?
        - what happens if LLM do not invoke any tools?
    """

    @classmethod
    def setUpClass(cls):
        print('\n\n# test_ollama_provider.py\n')
        load_dotenv()
        endpoint = os.environ.get('ENDPOINT')
        if not endpoint:
            print("\nPlease add ENDPOINT environment variable with Ollama endpoint")
            sys.exit(-1)

    @staticmethod
    def llm_query(llm, messages):
        for _ in llm.query(messages):
            pass

    @staticmethod
    def safe_issubclass(cls, parent):
        if cls is None:
            return False
        return issubclass(cls, parent)

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
            self.assertRaises(
                expected,
                Ollama.verify_messages_format,
                messages
            )

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
                inference_endpoint=endpoint
            )
            self.assertRaises(
                expected,
                self.llm_query,
                test_llm,
                messages
            )

    def test_tool_call(self):
        print()
        TR = ToolRegistry()
        CASES = {
            "unsupported_model":
                {
                    "input":
                        {
                            "model": "gemma2:9b",
                            "messages": [{"role": "assistant", "content": "What is the sum of 10 and 30?"}]
                        },
                    "expected": NotImplementedError
                },
            "no_tools_called":
                {
                    "input":
                        {
                            "model": "mistral",
                            "messages": [{"role": "assistant", "content": "What is the capital of France?"}]
                        },
                    "expected": None
                }
        }

        @TR.register(
            description="Sums two integer numbers"
        )
        def sum_tool(a: int, b: int) -> int:
            return a + b

        tools = [tool for tool in TR.marshal('base')]

        for case_name, case_input in CASES.items():
            test_input = case_input['input']
            expected = case_input['expected']
            print(f'Running case {case_name}\n\t- Input: {test_input}\n\t- Expected: {expected}')

            llm = Ollama(
                model=test_input['model'],
                inference_endpoint=os.environ['ENDPOINT']
            )

            if self.safe_issubclass(expected, BaseException):
                self.assertRaises(
                    NotImplementedError,
                    llm.tool_query,
                    test_input['messages'],
                    tools
                )
            else:
                result = llm.tool_query(test_input['messages'], tools)
                self.assertIsNone(
                    result,
                    f"Expected None got {result}"
                )


if __name__ == '__main__':
    unittest.main()
