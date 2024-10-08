"""Contains the class `Agent`, the core of the system."""
import json
import re
from json import JSONDecodeError

from tool_parse import ToolRegistry

from src.agent.llm import AVAILABLE_PROVIDERS, LLM, ProviderError
from src.agent.memory import Memory, Message, Role
from src.agent.plan import Plan, Task
from src.agent.prompts import PROMPTS, PROMPT_VERSION
from src.agent.tools import Tool


class Agent:
    """Penetration Testing Assistant"""

    def __init__(self, model: str,
                 tools: str = '',
                 llm_endpoint: str = 'http://localhost:11434',
                 provider: str = 'ollama',
                 provider_key: str = '',
                 tool_registry: ToolRegistry | None = None):
        """
        :param model: llm model name
        :param tools: documentation of penetration testing tools
        :param llm_endpoint: llm endpoint
        :param provider: llm provider
        :param provider_key: provider api key (if required)
        :param tool_registry: the available agent tools (ToolRegistry)
        """
        # Pre-conditions
        if provider not in AVAILABLE_PROVIDERS.keys():
            raise RuntimeError(f'{provider} not supported.')

        provider_class = AVAILABLE_PROVIDERS[provider]['class']
        key_required = AVAILABLE_PROVIDERS[provider]['key_required']
        if key_required and len(provider_key) == 0:
            raise RuntimeError(
                f'Missing PROVIDER_KEY environment variable for {provider}.'
            )

        # Agent Components
        self.llm = LLM(
            model=model,
            client_url=llm_endpoint,
            provider_class=provider_class,
            api_key=provider_key
        )
        self.mem = Memory()
        self.tool_registry: ToolRegistry | None = tool_registry
        if tool_registry is not None and len(tool_registry) > 0:
            self.tools = list(self.tool_registry.marshal('base'))
        else:
            self.tools = []

        # Prompts
        self._available_tools = tools
        prompts = PROMPTS[model][PROMPT_VERSION]
        self.system_plan_gen = prompts['plan']['system'].format(tools=tools)
        self.user_plan_gen = prompts['plan']['user']
        self.system_plan_con = prompts['conversion']['system']
        self.user_plan_con = prompts['conversion']['user']

    def query(self, sid: int, user_in: str):
        """Performs a query to the Large Language Model, will use RAG
        if provided with the necessary tool to perform rag search"""

        if not isinstance(user_in, str) or len(user_in) == 0:
            raise ValueError(f'Invalid input: {user_in} [{type(user_in)}]')

        # ensure session is initialized (otherwise llm has no system prompt)
        if sid not in self.mem.sessions.keys():
            self.new_session(sid)

        # get input for llm
        prompt = self.user_plan_gen.format(user=user_in)
        usr_msg = Message(Role.USER, prompt)
        self.mem.store_message(sid, usr_msg)
        messages = self.mem.get_session(sid).messages_to_dict_list()

        # call tools
        if self.tools:
            tool_response = self.llm.tool_query(
                messages,
                tools=self.tools
            )
            # tool results aren't persisted
            if tool_response['message'].get('tool_calls'):
                results = self.invoke_tools(tool_response)
                messages.extend(results)

        # generate response
        try:
            response = ''
            response_tokens = 0
            for chunk, tokens in self.llm.query(messages):
                yield chunk
                response += chunk

                if tokens[0] is not None:
                    pass  # store tokens count
        except ProviderError:
            raise

        # store response
        self.mem.store_message(
            sid,
            Message(Role.ASSISTANT, response, tokens=response_tokens)
        )

    def invoke_tools(self, tool_response):
        """Execute tools (ex. RAG) from llm response"""
        results = []

        call_stack = []
        for tool in tool_response['message']['tool_calls']:
            tool_meta = {
                'name': tool['function']['name'],
                'args': tool['function']['arguments']
            }

            if tool_meta in call_stack:
                continue
            try:
                res = self.tool_registry.compile(
                    name=tool_meta['name'],
                    arguments=tool_meta['args']
                )
                call_stack.append(tool_meta)
                results.append({'role': 'tool', 'content': str(res)})
            except Exception:
                pass

        return results

    def new_session(self, sid: int):
        """Initializes a new conversation"""
        self.mem.store_message(sid, Message(Role.SYS, self.system_plan_gen))

    def get_session(self, sid: int):
        """Open existing conversation"""
        return self.mem.get_session(sid)

    def get_sessions(self):
        """Returns list of Session objects"""
        return self.mem.get_sessions()

    def save_session(self, sid: int):
        """Saves the specified session to JSON"""
        self.mem.save_session(sid)

    def delete_session(self, sid: int):
        """Deletes the specified session"""
        self.mem.delete_session(sid)

    def rename_session(self, sid: int, session_name: str):
        """Rename the specified session"""
        self.mem.rename_session(sid, session_name)

    def extract_plan(self, plan_nl):
        """Converts a structured LLM response in a Plan object"""
        prompt = self.user_plan_con.format(query=plan_nl)
        messages = [
            {'role': 'system', 'content': self.system_plan_con},
            {'role': 'user', 'content': prompt}
        ]
        stream = self.llm.query(messages=messages)
        response = ''
        for chunk in stream:
            response += chunk

        try:
            plan_data = json.loads(response)
        except JSONDecodeError:
            # try extracting json from response
            json_regex = re.compile(r'\[.*?\]', re.DOTALL)
            json_match = json_regex.search(response)
            if json_match:
                plan_data = json.loads(json_match.group())
            else:
                print(f'PlanError:\n{response}')
                return None

        if not plan_data:
            raise RuntimeError(f'Error extracting plan: data not found.'
                               f'\nResponse: {response}')

        tasks = []
        for task in plan_data:
            if 'command' not in task.keys() or len(task['command']) == 0:
                continue
            if task['command'] == 'N/A':
                continue
            if task['command'].startswith('`'):
                cmd = task['command'][1:-1]
            else:
                cmd = task['command']

            tasks.append(Task(
                command=cmd,
                thought=task['thought'] if 'thought' in task else None,
                tool=Tool
            ))

        return Plan(tasks)

    def execute_plan(self, sid):
        """Extracts the plan from last message,
        stores it in memory and executes it."""
        session = self.mem.get_session(sid)

        messages = session.messages if session else None
        if not messages or len(messages) <= 1:
            return None

        msg = messages[-1] if messages[-1].role == Role.ASSISTANT \
            else messages[-2]

        try:
            plan = self.extract_plan(msg.content)
        except Exception as err:
            raise RuntimeError from err

        yield from plan.execute()

        self.mem.store_plan(sid, plan)
