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
    - gemma7b : ok
    - mistral : ok

    TODO: gemma2:9b, phi3:medium
    """
    MODELS = ['mistral', 'gemma:7b']

    def test_conversion(self):
        """Tests the conversion from natural language plan produced
        by the llm to tasks, so tests the efficiency of the prompt.
        """
        with open('test_cases/conversion.json', 'r', encoding='utf-8') as fp:
            test_cases = json.load(fp)

        inference_times = {model: {'times': [], 'mean': 0} for model in self.MODELS}
        for model in self.MODELS:
            agent = Agent(
                model=model,
                llm_endpoint=os.environ.get('ENDPOINT', 'http://localhost:11434')
            )
            for test_case in test_cases:
                plan_nl = test_case['content']
                expected_commands = test_case['commands']

                start = time.time()
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

                inference_times[model]['times'].append(t)

        with open('results/conversion_times_T4.json', 'w+', encoding='utf-8') as fp:
            for model in self.MODELS:
                mean_time = np.array(inference_times[model]['times']).mean()
                inference_times[model]['mean'] = mean_time
            json.dump(inference_times, fp)


if __name__ == "__main__":
    unittest.main()
