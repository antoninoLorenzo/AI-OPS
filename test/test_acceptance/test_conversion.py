import os
import json
import time
import unittest

import numpy as np
from dotenv import load_dotenv

from src.agent import Agent

load_dotenv()


class TestConversion(unittest.TestCase):
    """
    Conversion:
    - gemma7b   : ok
    - mistral   : ok
    - gemma3:9b : ok
    """
    MODELS = ['mistral', 'gemma:7b', 'gemma2:9b']

    def test_conversion(self):
        """Tests the conversion from natural language plan produced
        by the llm to tasks, so tests the efficiency of the prompt.
        """
        with open('test_cases/conversion.json', 'r', encoding='utf-8') as fp:
            test_cases = json.load(fp)

        for model in self.MODELS:
            agent = Agent(
                model=model,
                llm_endpoint=os.environ.get('ENDPOINT', 'http://localhost:11434')
            )
            for test_case in test_cases:
                plan_nl = test_case['content']
                expected_commands = test_case['commands']

                plan = agent.extract_plan(plan_nl)
                t = time.time() - start

                self.assertIsNotNone(plan, f"[{model}] Plan is None:")
                commands = [task.command for task in plan.tasks]
                self.assertEquals(
                    len(commands),
                    len(expected_commands),
                    f"[{model}] Found {len(commands)} commands, expected {len(expected_commands)}\n"
                    f"Commands:\n{commands}\nExpected:\n{expected_commands}"
                )

                for command in commands:
                    self.assertIn(
                        command,
                        expected_commands,
                        f"\n[{model}] Commands:\n{commands}\nExpected:\n{expected_commands}"
                    )


if __name__ == "__main__":
    unittest.main()
