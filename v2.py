from typing import Dict

from tool_parse import ToolRegistry

from src.agent import Architecture
from src.core import LLM, Conversation, Message, Role
from src.utils import get_logger


__LOGGER = get_logger(__file__)


class Default(Architecture):
    """
    Most basic implementation of Penetration Testing AI Assistant.

    TODO: actually define components (KISS)
    """
    def __init__(
        self,
        llm: LLM,
        prompts: Dict[str, str],
        tool_registry: ToolRegistry
    ):
        super().__init__()
        # check correct prompts are provided
        provided_prompts = list(prompts.keys())
        route, general, reason, tool =       \
            'router' in provided_prompts,    \
            'general' in provided_prompts,   \
            'reasoning' in provided_prompts, \
            'tool' in provided_prompts
        if not (route and general and reason and tool):
            expected = "router, general, reasoning, tool"
            raise ValueError(
                f'Error: expected prompts [{expected}]; received [{provided_prompts}]'
            )
        
        self.__llm: LLM = llm
        self.__prompts: Dict[str, str] = prompts
        self.__tool_registry: ToolRegistry = tool_registry
        self.__tools: tuple = tuple(self.__tool_registry.marshal('base'))

        __LOGGER.info(
            f'Initialized DefaultArchitecture: {llm.model}'
        )

    def query(
        self,
        conversation: Conversation
    ) -> Generator:
        """
        Generates response to last user message in Conversation.

        :param conversation: current conversation

        :returns: Generator with response text in chunks.
        """
        if conversation.messages[-1].role != Role.USER:
            raise ValueError(
                f"Expected last message with role='user'; got {conversation.messages[-1]}"
            )
        # TODO: design + implement

