import sys
import io
import re
import functools

import httpx
from rich.console import Console
from pytest import mark, fixture, fail

from cli.app import AppContext
from cli.impl import (
    __chat,                     # how do I test chat since its a REPL itself?
    __conversation_new,
    __conversation_load,
    __conversation_rename
)
from test.mock.mock_cli_prompt import build_input_mock


@fixture(scope="session")
def app_context():
    try:
        client = httpx.Client(base_url='http://127.0.0.1:8000')
        client.get('/ping', timeout=5)
    except Exception:
        fail("API not avaialble")

    context = AppContext(
        client=client,
        console=Console()
    )

    yield context

@fixture(scope="session")
def expected_regex():
    expected_success_regex = re.compile(r'^\[\d+\]:\s?\S.*') # [digit]: non-empty-string
    expected_failure_regex = re.compile(r'^Error:\s\S+.*')   # Error: non-empty-string
    yield {
        'success': expected_success_regex,
        'error': expected_failure_regex
    }


# TODO: add test cases (what could go wrong?)
@mark.parametrize('parameters', [
    {'conversation_name': 'some_convo'}
])
def test_conversation_new(
    app_context: AppContext,
    expected_regex,
    capfd,
    monkeypatch,
    parameters
):
    # when creating new conversation __chat is called automatically (feature).
    # prompt_toolkit.PromptSession is not compatible with PyTest, apparently.
    monkeypatch.setattr(
        'cli.impl.build_input_multiline', 
        functools.partial(build_input_mock, user_input='back')
    )

    __conversation_new(app_context, parameters['conversation_name'])
    capture = capfd.readouterr()
    assert re.match(expected_regex['success'], capture.out)


@mark.parametrize('parameters', [
    {'conversation_id': -1, 'expected': 'error'},
    {'conversation_id': 'not_a_number', 'expected': 'error'}
])
def test_conversation_load(
    app_context: AppContext,
    expected_regex,
    monkeypatch,
    capfd,
    parameters
):
    monkeypatch.setattr(
        'cli.impl.build_input_multiline', 
        functools.partial(build_input_mock, user_input='back')
    )

    __conversation_load(app_context, parameters['conversation_id'])
    capture = capfd.readouterr()
    assert re.match(expected_regex['error'], capture.out)


@mark.parametrize('parameters', [
    {'conversation_id': -1, 'new_name': 'valid'},
    {'conversation_id': 'not_a_number', 'new_name': 'valid'},
    {'conversation_id': 1, 'new_name': ''}
])
def test_conversation_rename(
    app_context: AppContext,
    expected_regex,
    capfd,
    parameters
):
    __conversation_rename(
        app_context, 
        parameters['conversation_id'],
        parameters['new_name']
    )

    capture = capfd.readouterr()
    assert re.match(expected_regex['error'], capture.out)


@mark.parametrize('parameters', [
    {'conversation_id': None, 'user_input': 'back', 'expected': 'success'},    
    {'conversation_id': -1, 'user_input': 'back', 'expected': 'error'},      
    {'conversation_id': 1, 'user_input': '', 'expected': 'error'}            
])
def test_chat(
    app_context: AppContext,
    expected_regex,
    capfd,
    monkeypatch,
    parameters
):
    monkeypatch.setattr(
        'cli.impl.build_input_multiline', 
        functools.partial(
            build_input_mock, 
            user_input=parameters['user_input']
        )
    )

    app_context.current_conversation_id = parameters['conversation_id']
    __chat(app_context)
    capture = capfd.readouterr()
    expected = parameters['expected']
    assert re.match(expected_regex[expected], capture.out)
