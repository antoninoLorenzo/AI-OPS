from dataclasses import dataclass

from src.agent.tools import Tool


@dataclass
class Task:
    """
    A Task represent a single unit of execution of a Tool with a specific command.
    The thought is the reason why the command should be executed.
    """
    thought: str
    tool: Tool
    command: str


@dataclass
class Plan:
    """Used to manage tasks."""
    tasks: list[Task]

    def execute(self):
        """Executes the tasks and yields the output of each task"""
        for task in self.tasks:
            print(f'Running: {task.command}\nReason: {task.thought}')
            out = task.tool.run(task.command)
            yield out
