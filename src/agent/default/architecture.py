import re
import json
from pathlib import Path
from typing import Dict, Generator, List, Optional

from tool_parse import ToolRegistry

from src.agent import Architecture
from src.core import (
    LLM, 
    Conversation, 
    Message, 
    Role, 
    ToolCall, 
    JSON_REGEX
)
from src.utils import get_logger

# setup logging
current = str(Path(__file__))
log_path = (
    Path(current[:current.find('AI-OPS')])
    / 'AI-OPS'
    / 'logs'
    / 'default_architecture.log'
)
LOGGER = get_logger(__name__, output_file=log_path)


class Default(Architecture):
    """
    Most basic implementation of Penetration Testing AI Assistant.

    It consists of a LLM + Function Calling (ex. search tool).

    Function Calling is implemented even if the LLM model doesn't natively support tool usage.
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
        route, general, tool =       \
            'router' in provided_prompts,    \
            'general' in provided_prompts,   \
            'tool' in provided_prompts
        if not (route and general and tool):
            expected = "router, general, tool"
            raise ValueError(
                f'Error: expected prompts [{expected}]; received [{provided_prompts}]'
            )
        
        # default architecture components
        self.__llm: LLM = llm
        self.__prompts: Dict[str, str] = prompts
        self.__tool_registry: ToolRegistry = tool_registry

        self.__query_map = {
            'native' : self.query_native,
            'routed' : self.query_routed
        }

        LOGGER.info(
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
        user_message = conversation.messages[-1]

        # select query strategy and get the generator
        response_stream = self.__query_map['routed'](conversation)
        # if self.__llm.support_tools:
        #     response_stream = self.__query_map['native'](conversation)
        # else:
        #     response_stream = self.__query_map['routed'](conversation)

        # note: input_tokens refers to the estimated size of last user message
        assistant_response = ''
        last_input_tokens, last_output_tokens = 0, 0
        for chunk, input_tokens, output_tokens in response_stream:
            yield chunk
            assistant_response += chunk
            last_input_tokens, last_output_tokens = input_tokens, output_tokens

        # reset user message (-> remove tool result) to reduce token consumption
        conversation.messages[-1] = user_message

        # store result in conversation
        conversation.messages[-1].set_tokens(last_input_tokens) # !!!: this includes the tool result
        conversation += Message(
            role=Role.ASSISTANT, 
            content=assistant_response, 
            token_length=output_tokens
        )

    def query_native(
        self,
        conversation: Conversation
    ):
        """
        Generates response with LLMs that support tool usage.

        :param conversation: current conversation

        :returns: Generator with tuples (text, user_message_tokens, output_tokens)
        """
        # The issue is that a query with ollama.Client using both tools and stream
        # will return either first chunk containing tool call OR normal stream.
        # Additionally the Ollama (Provider) implementation, that is abstracted by LLM
        # is implemented to make a clear distintion between normal query and tool query.
        raise NotImplementedError('only routed query is supported')

    def query_routed(
        self,
        conversation: Conversation
    ):
        """
        Generates response with LLMs that don't support tool usage.

        :param conversation: current conversation

        :returns: Generator with tuples (text, user_message_tokens, output_tokens)
        """
        user_message = conversation.messages[-1]
        system_prompt_key = self.get_assistant_prompt(user_message)
        
        if system_prompt_key == 'tool':
            # query llm to determine tool and parameters
            tool_call = self.tool_call(user_message)
            if tool_call is not None:
                # execute tool and append its output to user message
                tool_output = self.run_tool(tool_call)
                if tool_output is not None:
                    tool_result = (
                        f'\n\nadditional context: \n'
                        f'{tool_call.name}: {tool_call.parameters}\n{tool_output}'
                    )
                    conversation.messages[-1].content += tool_result
        
        # set system prompt
        system_prompt = self.__prompts[system_prompt_key]
        conversation.set_system_prompt(Message(role=Role.SYS, content=system_prompt))

        # run query
        yield from self.__llm.query(conversation)            

    def get_assistant_prompt(
        self,
        user_message: Message
    ) -> str:
        """
        Based on the last user message determines which prompt should be set as 
        system prompt, defining the behaviour of the Assistant; is mainly used to 
        determine if tool call is required for the current query.

        :param user_message: the last message in the conversation

        :return: the prompt key to select system prompt
        """
        try:
            router_prompt = self.__prompts['router']
            router_messages = Conversation(
                conversation_id=999,
                name='router_query',
                messages=[Message(role=Role.SYS, content=router_prompt), user_message]
            )

            assistant_prompt_key = ''
            response_stream = self.__llm.query(router_messages)
            for chunk, _, _ in response_stream:
                assistant_prompt_key += chunk
            
            # remove white-spaces and \n if present
            assistant_prompt_key = assistant_prompt_key.strip() 
            
            # default to general if selected key isn't correct 
            LOGGER.debug(f'router selected {assistant_prompt_key}')
            return assistant_prompt_key                             \
                if assistant_prompt_key in self.__prompts.keys()    \
                else 'general'
        except Exception as err:
            LOGGER.error(err)
            return 'general'

    def tool_call(
        self, 
        user_message: Message
    ) -> Optional[ToolCall]:
        """
        Query the LLM to provide a function call (used for models that don't support tool call).

        :param user_message: the last message in the conversation  

        :return: a single ToolCall or None
        """
        try:
            tool_prompt = self.__prompts['tool']
            tool_messages = Conversation(
                conversation_id=999,
                name='tool_query',
                messages=[Message(role=Role.SYS, content=tool_prompt), user_message]
            )

            tool_response = ''
            for chunk, _, _ in self.__llm.query(messages=tool_messages):
                tool_response += chunk
            
            # search for json in LLM resposne and extract the content
            tool_match = re.search(JSON_REGEX, tool_response)
            if not tool_match:
                error_message = (
                    f'Tool call failed: '
                    f'not found in LLM response: {tool_response}'
                )
                LOGGER.error(error_message)
                return None
            
            try:
                # fix response to be JSON
                tool_call_json = tool_match     \
                    .group(1)                   \
                    .replace("'", '"')          \
                    .strip()

                tool_call_dict = json.loads(tool_call_json)
                
                name: str = tool_call_dict['name']
                parameters: dict = tool_call_dict['arguments']
                return ToolCall(
                    name=name, 
                    parameters={
                        name: value 
                        for name, value in parameters.items()
                    }
                )

            except (json.JSONDecodeError, KeyError) as json_extract_err:
                error_message = (
                    f'Tool call failed: not found in LLM response: {tool_response}'
                    f'\nError: {json_extract_err}'
                )
                LOGGER.error(error_message)
                return None
        except Exception as err:
            LOGGER.error(err)
            return None
        
    def run_tool(
        self, 
        tool_call: ToolCall
    ) -> Optional[str]:
        try:
            LOGGER.info(f'calling {tool_call}')
            tool_call_dump = tool_call.model_dump()
            return self.__tool_registry.compile(
                name=tool_call_dump['name'],
                arguments=tool_call_dump['parameters']
            )
        except Exception as err:
            LOGGER.error(f'failed tool execution: {err}')
            return None

