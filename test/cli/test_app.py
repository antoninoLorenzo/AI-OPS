import re

from pytest import mark, fixture, fail

from cli.app import App
from test.mock.mock_cli_prompt import build_input_mock


@fixture
def commands():
    _commands = []
    yield _commands


@mark.parametrize('parameters', [
    {'available_commands': 0, 'command': 'some_command'},
    # test correct command but not found in registry (edge case)
    {'available_commands': 0, 'command': 'help'}
])
def test_commands_parsing(
    commands,
    monkeypatch,
    capfd,
    parameters
):
    monkeypatch.setattr(
        'cli.app.Prompt',
        build_input_mock('help')
    )
    expected_failure_regex = re.compile(r'^Error:\s\S+.*')

    app = App(
        api_url='http://127.0.0.1:8000',
        commands=commands[:parameters['available_commands']]
    )

    app.run()
    capture = capfd.readouterr()

    # remove the first message that is rendered when starting app
    start_pos = capture.out.find('Error')
    if start_pos == -1:
        fail('didn\'t get any error.')
    out = capture.out[start_pos:]
    
    assert re.match(expected_failure_regex, out)

