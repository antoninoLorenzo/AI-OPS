import os
import json
import time
import unittest

import numpy as np
from dotenv import load_dotenv

from src.agent import Agent

load_dotenv()


class TestPrompts(unittest.TestCase):
    MODELS = ['llama3']
    GEMINI_KEY = os.getenv('GEMINI_API_KEY')

    @unittest.skip('')
    def test_conversion(self):
        """Tests the conversion from natural language plan produced
        by the llm to tasks, so tests the efficiency of the prompt."""
        with open('test_cases/conversion.json', 'r', encoding='utf-8') as fp:
            test_cases = json.load(fp)

        inference_times = {model: {'times': [], 'mean': 0} for model in self.MODELS}
        for model in self.MODELS:
            agent = Agent(model=model)
            for test_case in test_cases:
                plan_nl = test_case['content']
                expected_commands = test_case['commands']

                start = time.time()
                plan = agent.extract_plan(plan_nl)
                t = time.time() - start

                self.assertIsNotNone(plan, "Plan is None:")
                commands = [task.command for task in plan.tasks]
                self.assertEquals(
                    len(commands),
                    len(expected_commands),
                    f"Found {len(commands)} commands, expected {len(expected_commands)}\n"
                    f"Commands:\n{commands}\nExpected:\n{expected_commands}"
                )
                self.assertEquals(
                    commands,
                    expected_commands,
                    f"Commands:\n{commands}\nExpected:\n{expected_commands}"
                )

                inference_times[model]['times'].append(t)

        with open('results/conversion_times.json', 'w+', encoding='utf-8') as fp:
            for model in self.MODELS:
                mean_time = np.array(inference_times[model]['times']).mean()
                inference_times[model]['mean'] = mean_time
            json.dump(inference_times, fp)

    # @unittest.skip('')
    def test_planning(self):
        """Tests the instruction following capability of the llm"""
        self.assertIsNotNone(self.GEMINI_KEY, 'Missing Gemini API Key')


if __name__ == "__main__":
    unittest.main()
