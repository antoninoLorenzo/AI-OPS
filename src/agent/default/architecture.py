import re
import json
from typing import Generator, Dict, Tuple

from tool_parse import ToolRegistry

from src.agent import Architecture
from src.core import Conversation
from src.core.llm import LLM
from src.core.memory import Message, Role
from src.utils import get_logger


logger = get_logger(__name__)


class State:
    """
    A class to manage the state of the LLM response stream.

    Attributes:
        SPEAKING (int): The assistant is currently generating a response.
        THINKING (int): The assistant is processing thoughts.
        IDLE (int): Indicates a transition between SPEAKING-THINKING.
    """
    SPEAKING = 1
    THINKING = 0
    IDLE = 2

    def __init__(self):
        self.__state = State.SPEAKING
        self.__count = 0

    def state(self, c: str):
        """:returns the state of the generation stream"""
        match self.__state:
            case State.SPEAKING:
                if c == '@':
                    # case it reached three @
                    if self.__count == 2:
                        self.__count = 0
                        self.__state = State.THINKING
                        return State.THINKING
                    # case it is parsing @
                    self.__count += 1
                    return State.IDLE
                else:
                    self.__count = 0
                    return State.SPEAKING
            case State.THINKING:
                if c == '@':
                    # case it reached three @
                    if self.__count == 2:
                        self.__count = 0
                        self.__state = State.SPEAKING
                        return State.IDLE
                    # case it is parsing #
                    self.__count += 1
                    return State.IDLE
                else:
                    self.__count = 0
                    return State.THINKING


class DefaultArchitecture(Architecture):
    """
    TODO: fix architecture since its kinda broken
        - search adds two user messages ???

    The overall code sucks. My bad.
    """
    model: str
    architecture_name = 'default'

    def __init__(
        self,
        llm: LLM,
        tools: ToolRegistry,
        prompts: Dict[str, str]
    ):
        super().__init__()
        self.llm: LLM = llm
        self.model = llm.model
        self.__tool_registry: ToolRegistry = tools
        self.__tools: tuple = tuple(self.__tool_registry.marshal('base'))
        self.__prompts = prompts

        # check they contain expected prompts 
        prompt_list = list(prompts.keys())
        route, general, reason, tool = \
            'router' in prompt_list, \
            'general' in prompt_list, \
            'reasoning' in prompt_list, \
            'tool' in prompt_list
        if not (route and general and reason and tool):
            raise ValueError('error initializing default architecture: prompts not found')
        
        self.__thought_parser: State = State()
        self.__tool_pattern = r"\s*({[^}]*(?:{[^}]*})*[^}]*}|\[[^\]]*(?:\[[^\]]*\])*[^\]]*\])\s*$"
        tool_names = ', '.join([
            tool["function"]["name"]
            for tool in self.__tools
        ])
        logger.info(
            f'Initialized DefaultArchitecture with model {llm.model} and tools {tool_names}'
        )

    def query(
        self,
        conversation: Conversation
    ) -> Generator:
        """Handles the input from the user and generates responses in a
        streaming manner.

        :param conversation: current conversation

        :returns: Generator with response text in chunks."""
        if conversation.messages[-1].role != Role.USER:
            raise ValueError("last message in conversation not a user message")

        user_input = conversation.messages[-1].content

        # route query
        assistant_index = self.__get_assistant_index(user_input)

        # RESPONSE
        prompt = self.__prompts['general']
        user_input_with_tool_call = f'{user_input}'
        if assistant_index == 2:
            prompt = self.__prompts['reasoning']
        elif assistant_index == 3:
            # Execute tool call and temporarily concatenate output to user
            # message, but the tool call result is thrown away (for simplicity)
            # in order to avoid display the result when load_session is called.
            tool_call_result: str | None = None
            tool_call_str: str | None = None
            for tool_call_execution in self.__tool_call(
                user_input,
                conversation,
            ):
                tool_call_state = tool_call_execution['state']
                if tool_call_state == 'error':
                    break
                elif tool_call_state == 'running':
                    # should inform client of tool execution ...
                    tool_call_str = tool_call_execution['message']
                else:
                    tool_call_result = tool_call_execution['message']

            if tool_call_result:
                user_input_with_tool_call += (
                    f'\n### TOOL {tool_call_str} ###\n'
                    f'{tool_call_result}\n'
                    f'### TOOL {tool_call_str} END ###'
                )
                assistant_index = 1

        # Replace system prompt with the one built for specific assistant type
        conversation.messages[0] = Message(role=Role.SYS, content=prompt)
        conversation += Message(
            role=Role.USER,
            content=user_input_with_tool_call
        )

        # note: conversation.message_dict doesn't care about context length
        response = ''
        # yes, I called ass_tokens the assistant tokens
        response_tokens = 0
        for chunk, usr_tokens, ass_tokens in self.llm.query(conversation):
            if usr_tokens:
                # set last message (usr) token usage
                conversation.messages[-1].set_tokens(usr_tokens)
                response_tokens = ass_tokens
                break
            if assistant_index == 1:
                response += chunk
                yield chunk
                continue

            for c in chunk:
                generation_state = self.__thought_parser.state(c)
                if generation_state == State.SPEAKING:
                    response += c
                    yield c
                # add thinking yield

        # remove tool call result from user input and add response to conversation
        conversation.messages[-1].content = user_input
        conversation += Message(
            role=Role.ASSISTANT,
            content=response,
        )

        conversation.messages[-1].set_tokens(response_tokens)
        logger.debug(f'CONVERSATION: {conversation}')

    def __get_assistant_index(
        self,
        user_input: str
    ) -> int:
        """Determine assistant index based on user input

        :param user_input: The user's input query.
        :return: An index to choose the proper prompt.
        """
        route_messages = Conversation(
            name='get_assistant_index',
            messages=[
                {'role': 'system', 'content': self.__prompts['router']},
                {'role': 'user', 'content': user_input}
            ]
        )
        assistant_index_buffer = ''
        for chunk, _, _ in self.llm.query(route_messages):
            if not chunk:
                break
            assistant_index_buffer += chunk
        try:
            return int(assistant_index_buffer.strip()[:1])
        except ValueError:
            logger.error(
                f'Wrong assistant index: {assistant_index_buffer}'
            )
            return 1

    def __tool_call(
        self,
        user_input: str,
        conversation: Conversation
    ):
        """Query a LLM for a tool call and executes it.

        :param user_input: The user's input query.
        :param conversation: The conversation history.

        :returns: Result of the tool execution."""
        # replace system prompt and generate tool call
        conversation.messages[0] = Message(
            role='system',
            content=self.__prompts['tool']
        )
        conversation += Message(
            role='user',
            content=user_input
        )

        tool_call_response = ''
        for chunk, _, _ in self.llm.query(conversation):
            tool_call_response += chunk

        # extract tool call and run it
        name, parameters, tool_extraction_error_message = self.__extract_tool_call(tool_call_response)
        if not name:
            yield {
                'name': name,
                'parameters': parameters,
                'state': 'error',
                'message': tool_extraction_error_message
            }
            return

        running_msg = (
            f"Running "
            f"{name.replace('_', ' ').capitalize()} "
            f"{list(parameters.values())[0]}"
        )
        logger.info(running_msg)
        yield {
            'name': name,
            'parameters': parameters,
            'state': 'running',
            'message': running_msg
        }
        try:
            tool_call_result = self.__tool_registry.compile(
                name=name,
                arguments=parameters
            )
            yield {
                'name': name,
                'parameters': parameters,
                'state': 'done',
                'message': tool_call_result
            }
            return
        except Exception as tool_exec_error:
            error_message = (
                f'({type(tool_exec_error).__name__}): tool execution failed, '
                f'{tool_exec_error}'
            )
            logger.error(error_message)
            yield {
                'name': name,
                'parameters': parameters,
                'state': 'error',
                'message': error_message
            }
            return

    def __extract_tool_call(
        self,
        tool_call_response: str
    ) -> Tuple[str | None, Dict, str | None]:
        """Extracts the tool call and its parameters from the LLM response.

        :param tool_call_response: The response containing a tool call.

        :returns:
            (tool name, parameters, None) OK
            (None, None, error_message) if extraction fails."""
        tool_call_match = re.search(self.__tool_pattern, tool_call_response)
        if not tool_call_match:
            error_message = (
                f'Tool call failed: '
                f'not found in LLM response: {tool_call_response}'
            )
            logger.error(error_message)
            return None, {}, error_message
        try:
            # fix response to be JSON
            tool_call_json = tool_call_match \
                .group(1) \
                .replace("'", '"') \
                .strip()

            tool_call_dict = json.loads(tool_call_json)
            name, parameters = tool_call_dict['name'], tool_call_dict['parameters']
        except json.JSONDecodeError as json_extract_err:
            error_message = (
                f'Tool call failed: not found in LLM response: {tool_call_response}'
                f'\nError: {json_extract_err}'
            )
            logger.error(error_message)
            return None, {}, error_message

        # check if tool exists
        found = False
        for t in self.__tools:
            if t['function']['name'] == name:
                found = True
        if not found:
            error_message = f'Tool call failed: {name} is not a tool.'
            logger.error(error_message)
            return None, {}, error_message

        return name, parameters, None
