# TODO:
# **query**
# - test streaming 
# - test token counting (**user_message_token_length**)
# 
# **tool_query**
#
import functools
from pytest import mark, raises, fixture

from src.core.llm import Ollama, ProviderError
from src.core.memory import Conversation, Message, Role
from test.mock.mock_ollama_client import MockOllamaClient


@mark.parametrize('parameters', [
    {'host_is_valid': False, 'model': 'mistral', 'exception': RuntimeError},
    {'host_is_valid': True, 'model': '', 'exception': ValueError},
    {'host_is_valid': True, 'model': 'chatgipiti', 'exception': ValueError},
])
def test_ollama_init(
    monkeypatch,
    parameters
):
    monkeypatch.setattr(
        'src.core.llm.ollama.Client',
        functools.partial(MockOllamaClient.__init__, valid_host=parameters['host_is_valid'])
    )
    
    with raises(parameters['exception']):
        Ollama(model=parameters['model'], inference_endpoint='')


# since Ollama.query uses pydantic.validate_call here the tests 
# are oriented to mess with Conversation.messages order and content.
@mark.parametrize('parameters', [
    {
        'conversation': Conversation(
            conversation_id=1,
            name='untitled',
            messages=[]
        ),
        'exception': ProviderError
    },
    {
        'conversation': Conversation(
            conversation_id=1,
            name='untitled',
            messages=[
                Message(role=Role.SYS, content='you are an helpful 41 ass')
            ]
        ),
        'exception': ProviderError
    },
    {
        'conversation': Conversation(
            conversation_id=1,
            name='untitled',
            messages=[
                Message(role=Role.USER, content='')
            ]
        ),
        'exception': ProviderError
    },
    {
        'conversation': Conversation(
            conversation_id=1,
            name='untitled',
            messages=[
                Message(role=Role.ASSISTANT, content='Shouldn\'t be an assistant message')
            ]
        ),
        'exception': ProviderError
    }
])
def test_query_message_validation(
    monkeypatch,
    parameters
):
    monkeypatch.setattr(
        'src.core.llm.ollama.Client',
        functools.partial(MockOllamaClient, valid_host=True)
    )

    ollama = Ollama(model='mistral', inference_endpoint='')
    with raises(parameters['exception']):
        for _ in ollama.query(parameters['conversation']):
            pass


@mark.parametrize('parameters', [
    {
        'conversation': Conversation(
            conversation_id=1,
            name='untitled',
            messages=[
                Message(role=Role.USER, content='Can I run LLM in a lemon?')
            ]
        ),
        'expected_length_user': 6,
        'expected_length_response': 10
    },
    {
        'conversation': Conversation(
            conversation_id=1,
            name='untitled',
            messages=[
                Message(role=Role.SYS, content='You are a large lemon engineer'),
                Message(role=Role.USER, content='Can I run LLM in a lemon?')
            ]
        ),
        'expected_length_user': 6,
        'expected_length_response': 10
    },
    {
        'conversation': Conversation(
            conversation_id=1,
            name='untitled',
            messages=[
                Message(role=Role.SYS, content='You are a large lemon engineer'),
                Message(role=Role.USER, content='Can I run LLM in a lemon?', token_length=6),
                Message(role=Role.ASSISTANT, content='hold on you might be onto something\n', token_length=9),
                Message(role=Role.USER, content='cool')
            ]
        ),
        'expected_length_user': 1,
        'expected_length_response': 4
    },

])
def test_query_response(
    monkeypatch,
    parameters
):
    monkeypatch.setattr(
        'src.core.llm.ollama.Client',
        functools.partial(MockOllamaClient, valid_host=True)
    )

    ollama = Ollama(model='mistral', inference_endpoint='')

    response = ''
    last_user, last_assistant = 0, 0
    for chunk, tk_user, tk_assistant in ollama.query(parameters['conversation']):
        response += chunk
        last_user = tk_user
        last_assistant = tk_assistant
    
    print(f'user: {last_user}; assistant: {last_assistant}')
    
    # the expected_length is approximated considering message token length is len(content) / 4 
    # => we expect len(user_message.content) / 4, len(response.content) / 4
    assert last_user == parameters['expected_length_user']
    assert last_assistant == int(len(response) / 4)
