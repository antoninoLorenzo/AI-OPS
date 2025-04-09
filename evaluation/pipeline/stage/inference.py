import json
from abc import ABC, abstractmethod
from enum import StrEnum
from pathlib import Path
from typing import Dict, Optional, List
from dataclasses import dataclass

from pydantic import ConfigDict
from tool_parse import ToolRegistry

from evaluation.core import QueueStream, Stage, Task
from evaluation.core import gen_checkpoint_id, verify_checkpoint_id
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
    overwrite_checkpoints: bool = False

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


class ConversationType(StrEnum):
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
    assistant_type: str
    assistant_model: str
    conversation: Conversation
    conversation_type: ConversationType

    model_config = ConfigDict(arbitrary_types_allowed=True)


class Inference(Stage):
    """
    Implements the Inference Stage execution logic.
    """

    def __init__(self, overwrite_checkpoints: bool = False):
        current = str(Path(__file__))
        self.__checkpoints_path = (
            Path(current[:current.find('evaluation')])
            / 'evaluation'
            / 'resources'
            / 'checkpoints'
        )
        self.__overwrite_checkpoints = overwrite_checkpoints if overwrite_checkpoints is True else False
        LOGGER.info(f'inference stage: skipping checkpoints: {self.__overwrite_checkpoints}')
        
        if not self.__checkpoints_path.exists():
            self.__checkpoints_path.mkdir()
        
        # remove checkpoints if overwrite is specified
        if self.__overwrite_checkpoints:
            for p in self.__checkpoints_path.iterdir():
                p.unlink()
            LOGGER.info(f'inference stage: deleted checkpoints in {self.__checkpoints_path}')

    def run(self, task_stream: QueueStream):
        # TODO: there information about assistant is yielded with conversation, however its getting out of hand
        try:
            for task in task_stream:
                if not isinstance(task, InferenceTask):
                    raise ValueError(f'expected InferenceTask: got {type(task)}')
                LOGGER.debug(f'inference stage: received conversation {task.conversation.name}')
                
                conversation = task.conversation
                architecture_name = task.assistant.architecture_name
                architecture_model = task.assistant.model
                conversation_type = task.conversation_type

                # generate a unique identifier for the current converstaion taking
                # into account assistant architecture, model and the conversation type
                conversation_identifier = gen_checkpoint_id(
                    architecture_name, 
                    architecture_model, 
                    conversation.name, 
                    conversation_type
                )

                conversation_checkpoint = Path(
                    self.__checkpoints_path 
                    / f'{conversation_identifier}.json'
                )
                
                # check if conversation is already generated
                if conversation_checkpoint.exists() and not self.__overwrite_checkpoints:
                    with open(str(conversation_checkpoint), 'r') as fp:
                        c_conversation = Conversation.model_validate(json.load(fp))
                    LOGGER.info(f'loaded checkpoint for conversation : {c_conversation.name}')
                    
                    yield c_conversation, task.assistant_type, task.assistant_model
                    continue

                # generate multi-turn conversation
                if task.conversation_type == ConversationType.MultiTurn:
                    raise NotImplementedError('logic to generate an entire conversation is missing.')
                
                # generate single-turn conversation
                # note: Assistant query method handles adding response to the conversation itself.
                _ = task.assistant.query(conversation=conversation)
                yield conversation, task.assistant_type, task.assistant_model

                # save conversation as checkpoint
                with open(str(conversation_checkpoint), 'w') as fp:
                    json.dump(conversation.model_dump(), fp)
                    LOGGER.info(f'saved conversation {conversation.name} to {conversation_checkpoint}')
        except Exception as err:
            raise RuntimeError(f'exit: error in the Inference Stage: {err}')

