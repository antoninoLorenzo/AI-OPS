from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path
from typing import Dict, Optional, List
from dataclasses import dataclass

from pydantic import ConfigDict
from tool_parse import ToolRegistry

from evaluation.core import QueueStream, Stage, Task
from src.agent.default import Default, init_default_architecture
from src.core import LLM, TOOL_REGISTRY, Conversation
from src.utils import get_logger


current = str(Path(__file__))
log_path = (
    Path(current[:current.find('evaluation')])
    / 'evaluation'
    / 'logs'
    / 'inference.log'
)
LOGGER = get_logger(__name__, output_file=log_path)


@dataclass
class InferenceSettings:
    architecture: str
    models: List[str]
    inference_endpoint: str

    def __str__(self):
        mdls = ', '.join(self.models)
        return (
            f"architecture: {self.architecture}; endpoint: {self.inference_endpoint}; "
            f"models: {mdls}"
        )


class InferenceExecutor(ABC):
    """
    Models a generic LLM based component that must be evaluated.  
    """
    model: str
    architecture_name: str

    @abstractmethod
    def query(self, conversation: Conversation):
        pass


class AssistantFactory(ABC):
    """
    Represents a generic Factory used for the creation of a LLM component.
    """

    @abstractmethod
    def build_assistant(self, *args, **kwargs) -> InferenceExecutor:
        """
        Setup an InferenceExecutor and sets its `model` name and `architecture_name`.
        """


class DefaultAssistant(InferenceExecutor):
    """
    Inference component that wraps the AI-OPS Default assistant.
    """

    def __init__(
        self, 
        llm: LLM, 
        tool_registry: ToolRegistry,
        prompts: Optional[Dict[str, str]] = None,
    ):
        # if for some reason other prompts should be provided, let's say for testing, 
        # we can do it there and run the evaluation; if the prompts for each component
        # are not provided (router, general, tool) Default will raise ValueError
        if prompts is None:
            self.architecture = init_default_architecture(llm=llm, tool_registry=tool_registry)
        else:
            self.architecture = Default(llm=llm, prompts=prompts, tool_registry=tool_registry)
        
        self.model = self.architecture.model
        self.architecture_name = self.architecture.architecture_name

    def query(self, conversation: Conversation):
        response = ''
        for chunk in self.architecture.query(conversation):
            response += chunk
        # the query method updates the conversation by itself; is it a good choice?
        return response


class DefaultAssistantFactory(AssistantFactory):
    """
    Builds the Default AI-OPS assistant. 
    """

    def build_assistant(self, model: str, inference_endpoint: str):
        llm = LLM(model=model, inference_endpoint=inference_endpoint)
        return DefaultAssistant(llm=llm, tool_registry=TOOL_REGISTRY)


class ConversationType(Enum):
    """
    Specifies the scenario for the InferenceTask, there are two evaluation scenarios:
    - single-turn: 
        a single response is generated and put it the conversation, used to evaluate 
        the assistant on single-turn metrics such as Hallucination.
    - multi-turn: 
        multiple-turns are generated and put in the conversation, used to evaluate the
        assistant on multi-turn metrics such as RoleAdherence or KnowledgeRetention.
    """
    SingleTurn: str = 'single-turn'
    MultiTurn: str = 'multi-turn'


class InferenceTask(Task):
    """
    Represents the input for the Inference Stage.

    :param assistant: the LLM-based component to evaluate.
    :param conversation: contains the user input (test-case).
    :param conversation_type: tells the inference stage the type of conversation to generate.
    """
    # The inference stage is completely decoupled from the specific component being
    # tested, also it shouldn't be responsible for creation of the said component.
    assistant: InferenceExecutor
    conversation: Conversation
    conversation_type: ConversationType

    model_config = ConfigDict(arbitrary_types_allowed=True)


class Inference(Stage):
    """
    Implements the Inference Stage execution logic.
    """

    def run(self, task_stream: QueueStream):
        try:
            for task in task_stream:
                if not isinstance(task, InferenceTask):
                    raise ValueError(f'expected InferenceTask: got {type(task)}')
                
                LOGGER.debug(f'inference stage: received conversation id {task.conversation.conversation_id}')
                
                if task.conversation_type == ConversationType.MultiTurn:
                    raise NotImplementedError('logic to generate an entire conversation is missing.')
                
                conversation = task.conversation
                response = task.assistant.query(conversation=conversation)

                # maybe should use a Stream, but for now let's work with Generators
                yield conversation
        except Exception as err:
            # If anything goes wrong there we want to (1) fail gracefully (2) save checkpoints.
            # Note: all of that is handled by the pipeline orchestrator (not Stage responsibility).
            raise RuntimeError(f'exit: error in the Inference Stage: {err}')

