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
    __conversation_save,
    __conversation_delete,
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


# TODO: add test cases (what could go wrong?)
@mark.parametrize('parameters', [
    {'conversation_name': 'some_convo'}
])
def test_conversation_new(
    app_context: AppContext,
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
    expected_success_regex = re.compile(r'^\[\d+\]:\s?\S.*') # [digit]: non-empty-string
    expected_failure_regex = re.compile(r'^Error:\s\S+.*') 

    __conversation_new(app_context, parameters['conversation_name'])

    capture = capfd.readouterr()
    assert re.match(expected_success_regex, capture.out)


@mark.parametrize('parameters', [
    {'conversation_id': -1, 'expected': 'error'},
    {'conversation_id': 'not_a_number', 'expected': 'error'}
])
def test_conversation_load(
    app_context: AppContext,
    monkeypatch,
    capfd,
    parameters
):
    monkeypatch.setattr(
        'cli.impl.build_input_multiline', 
        functools.partial(build_input_mock, user_input='back')
    )
    expected_failure_regex = re.compile(r'^Error:\s\S+.*') 

    __conversation_load(app_context, parameters['conversation_id'])

    capture = capfd.readouterr()
    assert re.match(expected_failure_regex, capture.out)


@mark.parametrize('parameters', [
    {'conversation_id': -1, 'new_name': 'valid'},
    {'conversation_id': 'not_a_number', 'new_name': 'valid'},
    {'conversation_id': 1, 'new_name': ''}
])
def test_conversation_rename(
    app_context: AppContext,
    capfd,
    parameters
):
    expected_failure_regex = re.compile(r'^Error:\s\S+.*') 

    __conversation_rename(
        app_context, 
        parameters['conversation_id'],
        parameters['new_name']
    )

    capture = capfd.readouterr()
    assert re.match(expected_failure_regex, capture.out)
