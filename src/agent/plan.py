import json
from dataclasses import dataclass
from enum import StrEnum

from src.agent.tools import Tool


class TaskStatus(StrEnum):
    """Represent the possible states of execution for a Task"""
    WAITING = 'Waiting'
    RUNNING = 'Running'
    DONE = 'Done'


@dataclass
class Task:
    """
    A Task represent a single unit of execution of a Tool with a specific
    command. The thought is the reason why the command should be executed.
    """
    thought: str
    tool: Tool
    command: str
    status: TaskStatus = TaskStatus.WAITING
    output: str = ''

    def __str__(self):
        return f"Task: {self.command}\nStatus: ({self.status})"


@dataclass
class Plan:
    """Used to manage tasks."""
    tasks: list[Task]

    @staticmethod
    def from_str(text: str):
        """Converts a structured LLM response in a Plan object"""

    def execute(self):
        """Executes the tasks and yields the output of each task"""
        for task in self.tasks:
            task.status = TaskStatus.RUNNING

            yield self.tasks

            task.output = task.tool.run(task.command)
            task.status = TaskStatus.DONE

        yield self.tasks
