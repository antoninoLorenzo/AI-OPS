import json
import unittest

from src.agent import Agent
from src.agent.tools import Terminal
from src.agent.plan import Plan, Task, TaskStatus


class TestPlan(unittest.TestCase):

    # def test_execute(self):
    #     tasks = [
    #         Task(thought="Get directory content", tool=Terminal, command="ls"),
    #         Task(thought="Get machine host name", tool=Terminal, command="hostname")
    #     ]

    #     plan = Plan(tasks)
    #     for output in plan.execute():
    #         print('---------------------------------')
    #         for i, task_overview in enumerate(output):
    #             print(f'{i+1}. {task_overview}')
    #             if task_overview.status == TaskStatus.DONE:
    #                 print(f'Output:\n{task_overview.output}')

    def test_from_response(self):
        agent = Agent(model='llama3')
        with open('plan_tests.json', 'r', encoding='utf-8') as fp:
            test_cases = json.load(fp)

        for test_case in test_cases:
            plan_nl = test_case['content']
            expected_commands = test_case['commands']

            plan = agent.extract_plan(plan_nl)
            self.assertIsNotNone(plan, "Plan is None:")

            commands = [task.command for task in plan.tasks]

            self.assertEquals(
                len(commands),
                len(expected_commands),
                f"commands {len(commands)} != expected {len(expected_commands)}"
            )
            self.assertEquals(
                commands,
                expected_commands,
                f"Commands:\n{commands}\nExpected:\n{expected_commands}"
            )



    # def test_should_timeout(self):
    #     pass

    # def test_multi_step_task(self):
    #     pass


if __name__ == "__main__":
    unittest.main()
