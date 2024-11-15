import re
import json
import logging
from typing import Generator, Dict, Tuple

from tool_parse import ToolRegistry

from src.agent import AgentArchitecture
from src.core.llm import LLM
from src.core.memory import Message, Role

logger = logging.getLogger(__name__)

formatter = logging.Formatter('%(levelname)s: %(name)s: %(message)s')

logger_handler = logging.StreamHandler()
logger_handler.setLevel(logging.DEBUG)
logger_handler.setFormatter(formatter)

logger.setLevel(logging.DEBUG)
logger.addHandler(logger_handler)


class State:
    """
    A class to manage the state of the LLM response stream.

    Attributes:
        SPEAKING (int): Indicates the assistant is currently generating a response.
        THINKING (int): Indicates the assistant is processing thoughts.
        IDLE (int): Indicates a transition between SPEAKING-THINKING.
    """
    SPEAKING = 1
    THINKING = 0
    IDLE = 2

    def __init__(self):
        self.__state = State.SPEAKING
        self.__count = 0

    def state(self, c: str):
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


class DefaultArchitecture(AgentArchitecture):

    def __init__(
        self,
        llm: LLM,
        tools: ToolRegistry,
        router_prompt: str,
        general_prompt: str,
        reasoning_prompt: str,
        tool_prompt: str
    ):
        super().__init__()
        self.llm: LLM = llm
        self.__tool_registry: ToolRegistry = tools
        self.__tools: tuple = tuple(self.__tool_registry.marshal('base'))
        self.__prompts: Dict[str, str] = {
            'router': router_prompt,
            'general': general_prompt,
            'reasoning': reasoning_prompt,
            'tool': tool_prompt
        }

        self.__thought_parser: State = State()
        self.__tool_pattern = r"\s*({[^}]*(?:{[^}]*})*[^}]*}|\[[^\]]*(?:\[[^\]]*\])*[^\]]*\])\s*$"

        logger.debug(
            '\nInitialized DefaultArchitecture'
            f'\nModel: {llm.model}'
            f'\nTools: {self.__tools}'
        )

    def query(
        self,
        session_id: int,
        user_input: str
    ) -> Generator:
        """Handles the input from the user and generates responses in a
        streaming manner.

        :param session_id: The session identifier.
        :param user_input: The user's input query.

        :returns: Generator with response text in chunks."""
        # create a new conversation if not exists
        if not self.memory.get_session(session_id):
            self.new_session(session_id)

        # route query
        assistant_index = self.__get_assistant_index(user_input)

        # RESPONSE
        prompt = self.__prompts['general']
        if assistant_index == 2:
            prompt = self.__prompts['reasoning']
        elif assistant_index == 3:
            tool_call_result = self.__tool_call(
                user_input,
                self.memory.get_session(session_id).message_dict,
            )
            if len(tool_call_result) == 0:
                logger.error('Tool call failed, will answer without tool results.')

            user_input += f'Web Search Result:\n{tool_call_result}'
            assistant_index = 1

        history = self.memory.get_session(session_id)
        history.messages[0] = Message(role=Role.SYS, content=prompt)
        history.add_message(
            Message(
                role=Role.USER,
                content=user_input
            )
        )

        # note: history.message_dict doesn't care about context length
        response = ''
        for chunk, ctx_length in self.llm.query(history.message_dict):
            if ctx_length:
                break
            if assistant_index == 1:
                response += chunk
                yield chunk
                continue

            for c in chunk:
                generation_state = self.__thought_parser.state(c)
                if generation_state == State.SPEAKING:
                    yield c

    def new_session(self, session_id: int):
        """Create a new conversation if not exists"""
        # logger.debug('Creating new session')
        self.memory.store_message(
            session_id,
            Message(
                role=Role.SYS,
                content=self.__prompts['general']
            )
        )

    def __get_assistant_index(
        self,
        user_input: str
    ) -> int:
        """Determine assistant index based on user input

        :param user_input: The user's input query.
        :return: An index to choose the proper prompt.
        """
        route_messages = [
            {'role': 'system', 'content': self.__prompts['router']},
            {'role': 'user', 'content': user_input}
        ]
        assistant_index_buffer = ''
        for chunk, _ in self.llm.query(route_messages):
            if not chunk:
                break
            assistant_index_buffer += chunk
        try:
            return int(assistant_index_buffer.strip()[:1])
        except ValueError:
            logger.error(
                f'\nWrong assistant index: {assistant_index_buffer}'
                '\nWill use default index: 1'
            )
            return 1

    def __tool_call(
        self,
        user_input: str,
        message_history: list
    ) -> str:
        """Query a LLM for a tool call and executes it.

        :param user_input: The user's input query.
        :param message_history: The conversation history.

        :returns: Result of the tool execution."""
        message_history[0] = {'role': 'system', 'content': self.__prompts['tool']}
        message_history.append({'role': 'user', 'content': user_input})

        tool_call_response = ''
        for chunk, _ in self.llm.query(message_history):
            tool_call_response += chunk

        name, parameters = self.__extract_tool_call(tool_call_response)
        if not name:
            return ''

        logger.debug(f'Calling {name} with {parameters}).')
        try:
            tool_call_result = self.__tool_registry.compile(
                name=name,
                arguments=parameters
            )
            return tool_call_result
        except Exception as tool_exec_error:
            logger.error(f'Tool execution failed: {tool_exec_error}')
            return ''

    def __extract_tool_call(
        self,
        tool_call_response: str
    ) -> Tuple[str | None, Dict]:
        """Extracts the tool call and its parameters from the LLM response.

        :param tool_call_response: The response containing a tool call.

        :returns:
            (tool name, parameters) OK
            (None, None) if extraction fails."""
        tool_call_match = re.search(self.__tool_pattern, tool_call_response)
        if not tool_call_match:
            logger.error(
                '\nTool call failed: not found in LLM response.'
                f'\nResponse: {tool_call_response}'
            )
            return None, {}
        try:
            # fix response to be JSON
            tool_call_json = tool_call_match \
                .group(1) \
                .replace('"', '')
            tool_call_json = tool_call_json \
                .replace("'", '"')

            tool_call_dict = json.loads(tool_call_json)
            name, parameters = tool_call_dict['name'], tool_call_dict['parameters']
        except json.JSONDecodeError as json_extract_err:
            logger.error(
                '\nTool call failed: not found in LLM response.'
                f'\nResponse: {tool_call_response}'
                f'\nError: {json_extract_err}'
            )
            return None, {}

        # check if tool exists
        found = False
        for t in self.__tools:
            if t['function']['name'] == name:
                found = True
        if not found:
            logger.error(f'Tool call failed: {name} is not a tool.')
            return None, {}
        return name, parameters

