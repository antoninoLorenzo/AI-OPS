from pytest import mark, raises

from cli.commands import CommandParser, ParserException


base_command_parameters = [
    {'command': ''},
    {'command': ' '},
    {'command': 'not_exist'}
]

conversation_command_parameters = [
    {'command': 'conversation'},
    {'command': 'conversation not_exist'},
    {'command': 'conversation load'},
    {'command': 'conversation load not_id'},
    {'command': 'conversation rename name_is_second not_id'},
    {'command': 'conversation save not_id'},
    {'command': 'conversation delete not id_split'},
    {'command': 'conversation list extra_param'},
    {'command': 'conversation new some_name extra_param'}
]


@mark.parametrize('parameters', base_command_parameters)
def test_base_command(parameters: dict):
    parser = CommandParser()
    command = parameters['command']

    with raises(ParserException):
        parser.parse(command)


@mark.parametrize('parameters', conversation_command_parameters)
def test_conversation_command(parameters: dict):
    parser = CommandParser()
    command = parameters['command']

    with raises(ParserException):
        parser.parse(command)

