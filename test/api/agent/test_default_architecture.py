import functools

from tool_parse import ToolRegistry
from pytest import mark, fixture, raises

from src.agent.utils import load_prompts
from src.agent.default import Default
from src.core import LLM, Conversation, Message, Role, ToolCall, ProviderError
from test.mock.mock_ollama_client import MockOllamaClient
from test.mock.mock_search import MockSearch


@fixture(scope='session')
def prompts():
    # prompts can be loaded once
    yield load_prompts()


@mark.parametrize('parameters', [
    {
        # test what happen if no tools where provided
        'user_message': Message(role=Role.USER, content='What are recent FastAPI CVEs?'),
        'tools': None,
        'llm_response': '',
        'expected': None  # remember __tool_call returns Optional[ToolCall]
    },
    {
        # test what happens if LLM gives answer that is not JSON
        'user_message': Message(role=Role.USER, content='What are recent FastAPI CVEs?'),
        'tools': 'search',
        'llm_response': 'the response needs to contain json text',
        'expected': None
    },
    {
        # test what happens if LLM gives answer that is JSON but key names are wrong
        'user_message': Message(role=Role.USER, content='What are recent FastAPI CVEs?'),
        'tools': 'search',
        'llm_response': '{"name": "search_web", "parameters": {"search_query": "some_query"}}',
        'expected': None
    },
    {
        'user_message': Message(role=Role.USER, content='What are recent FastAPI CVEs?'),
        'tools': 'search',
        'llm_response': '{"name": "search_web", "arguments": {"search_query": "some_query"}}',
        'expected': ToolCall
    }
])
def test_tool_call(
    monkeypatch,
    prompts,
    parameters
):
    """
    testing how __tool_call handles failures
    """
    # initialize components for architecture, thats done for each test because
    # llm_response from parameters should be injected in the mock Ollama client.
    monkeypatch.setattr(
        'src.core.llm.ollama.Client',
        functools.partial(
            MockOllamaClient, 
            default_message=parameters['llm_response']
        )
    )

    llm = LLM(
        model='mistral',
        inference_endpoint='some_endpoint'
    )

    tool_registry = ToolRegistry()

    # initializing this way isn't really great
    if parameters['tools'] is not None:
        search = MockSearch()

        @tool_registry.register(description=search.usage)
        def search_web(search_query: str):
            return search.run(search_query)
    
    # run test
    architecture = Default(
        llm=llm,
        prompts=prompts,
        tool_registry=tool_registry
    )

    tool_call = architecture.tool_call(parameters['user_message'])
    if parameters['expected'] is None:
        assert tool_call is None
    else:
        assert isinstance(tool_call, parameters['expected'])


@mark.parametrize('parameters', [
    {
        # when Ollama Client raises any error the Provider Error 
        # should be propagated to the higher level query method.
        'user_message': Message(role=Role.USER, content='What are recent FastAPI CVEs?'),
        'assistant_prompt_result': 'general',
        'tool_call_result': None,
        'tool_execution_result': None,
        'expected': ProviderError
    },
    {
        # when the router selects tool prompt but no ToolCall is
        # generated the assistant should generate a response normally
        'user_message': Message(role=Role.USER, content='What are recent FastAPI CVEs?'),
        'assistant_prompt_result': 'tool',
        'tool_call_result': None,
        'tool_execution_result': None,
        'expected': 'response for: What are recent FastAPI CVEs?'
    },
    {
        # when tool execution fails a response should be generated normally
        'user_message': Message(role=Role.USER, content='What are recent FastAPI CVEs?'),
        'assistant_prompt_result': 'tool',
        'tool_call_result': ToolCall(
            name='search_web', 
            parameters={'search_query': 'FastAPI CVEs'}
        ),
        'tool_execution_result': None,
        'expected': 'response for: What are recent FastAPI CVEs?'
    }
])
def test_query_routed(
    monkeypatch,
    prompts,
    parameters
):
    # replace get_assistant_prompt and tool_call to isolate query_routed
    monkeypatch.setattr(
        'src.agent.default.architecture.Default.get_assistant_prompt',
        lambda _, user_message: parameters['assistant_prompt_result']
    )

    monkeypatch.setattr(
        'src.agent.default.architecture.Default.tool_call',
        lambda _, user_message: parameters['tool_call_result']
    )
    
    # initialize architecture components
    if parameters['expected'] == ProviderError:
        client = functools.partial(MockOllamaClient, raise_provider_error=True)
    else:
        client = MockOllamaClient
        
    monkeypatch.setattr('src.core.llm.ollama.Client', client) 
    llm = LLM(model='mistral', inference_endpoint='some_endpoint')
    tool_registry = ToolRegistry()

    # register MockSearch.run in the tool registry
    if tool_execution_result := parameters['tool_execution_result'] is None:
        search = MockSearch(should_fail=True)
    else:
        search = MockSearch() # no test case currently 

    @tool_registry.register(description=search.usage)
    def search_web(search_query: str):
        return search.run(search_query)
    
    # create input conversation
    conversation = Conversation(
        conversation_id=1,
        name='untitled',
        messages=[parameters['user_message']]
    )

    # run test
    architecture = Default(
        llm=llm,
        prompts=prompts,
        tool_registry=tool_registry
    )

    # for some reason isinstance won't work
    if parameters['expected'] == ProviderError:
        with raises(parameters['expected']):
            for _ in architecture.query_routed(conversation):
                pass
    else:
        assistant_response = ''
        for chunk, _, _ in architecture.query_routed(conversation):
            assistant_response += chunk
        assert assistant_response == parameters['expected']
