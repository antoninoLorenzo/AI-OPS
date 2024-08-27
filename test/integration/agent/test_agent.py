import os
import sys
import unittest

from dotenv import load_dotenv

from src.agent.agent import Agent


class TestAgent(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        load_dotenv()
        if os.getenv('ENDPOINT') is None:
            print('\nMissing ENDPOINT environment variable.')
            sys.exit(1)

    @staticmethod
    def query(agent, sid, user_in):
        for _ in agent.query(sid, user_in):
            pass

    def test_query(self):
        print()
        CASES = {
            "empty_input":
                {
                    "input": {"user_in": ""},
                    "agent": {
                        "model": "mistral",
                        "endpoint": os.getenv('ENDPOINT')
                    },
                    "expected": ValueError
                },
            "not_str_input":
                {
                    "input": {"user_in": 10},
                    "agent": {
                        "model": "mistral",
                        "endpoint": os.getenv('ENDPOINT')
                    },
                    "expected": ValueError
                },
            "unreachable_endpoint":
                {
                    "input": {"user_in": "Hi"},
                    "agent": {
                        "model": "mistral",
                        "endpoint": "http://localhost:54321"
                    },
                    "expected": RuntimeError
                }
        }

        i = 0
        for case_name, case_input in CASES.items():
            user_in: str = case_input["input"]["user_in"]
            model: str = case_input["agent"]["model"]
            endpoint: str = case_input["agent"]["endpoint"]
            expected = case_input["expected"]
            print(f'Running case {case_name}\n\t- Input: {case_input}\n\t- Expected: {expected}')

            agent = Agent(model=model, llm_endpoint=endpoint)
            self.assertRaises(
                expected,
                self.query,
                agent,
                i,
                user_in
            )

            i += 1

    @unittest.skip
    def test_invoke_tools(self):
        pass


if __name__ == "__main__":
    pass
