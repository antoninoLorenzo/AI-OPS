from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel


class Task(BaseModel):
    """
    Instance of a processing task for a Stage.
    """

class Stream(ABC):
    """
    Represents a stream of data.
    """
    
    @abstractmethod
    def send(self, result: Any):
        pass


class Stage(ABC):
    """
    Define a stage in a data processing pipeline. 

    It receives data to process from the Orchestrator and sends the output in the OutputStream.
    """

    @abstractmethod
    def run(self, task_stream: Stream):
        pass
