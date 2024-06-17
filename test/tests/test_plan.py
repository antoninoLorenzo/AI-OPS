import unittest

from src.agent.plan import Plan, Task, TaskStatus
from src.agent.tools import Terminal


class TestPlan(unittest.TestCase):

    def test_from_response(self):
        pass

    def test_execute(self):
        tasks = [
            Task(thought="Get directory content", tool=Terminal, command="ls"),
            Task(thought="Get machine host name", tool=Terminal, command="hostname")
        ]

        plan = Plan(tasks)
        for output in plan.execute():
            print('---------------------------------')
            for i, task_overview in enumerate(output):
                print(f'{i+1}. {task_overview}')
                if task_overview.status == TaskStatus.DONE:
                    print(f'Output:\n{task_overview.output}')

    def test_should_timeout(self):
        pass

    def test_multi_step_task(self):
        pass


if __name__ == "__main__":
    unittest.main()
