from dataclasses import dataclass
from src.agent.tools import Tool


@dataclass
class Task:
    thought: str
    tool: Tool
    command: str


@dataclass
class Plan:
    tasks: list[Task]

    def execute(self):
        for task in self.tasks:
            print(f'Running: {task.command}\nReason: {task.thought}')
            out = task.tool.run(task.command)
            yield out
