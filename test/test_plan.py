import unittest

from src.agent.plan import Plan, Task
from src.agent.tools import Terminal


class TestPlan(unittest.TestCase):
    def test_execute(self):
        tasks = [
            Task(thought="Get directory content", tool=Terminal, command="ls")
        ]

        plan = Plan(tasks)
        for output in plan.execute():
            print(output)


if __name__ == "__main__":
    unittest.main()
