import json
from pytest import fixture, mark
from src.core.memory.schema import Message, Role, Conversation


@fixture
def conversations_test_cases(tmp_path):
    conversation_empty = Conversation(
        conversation_id=1,
        name='test conversation empty',
        messages=[]
    )
    conversation_full = Conversation(
        conversation_id=2,
        name='test conversation full',
        messages=[
            Message(role=Role.SYS, content='You are an expert AI Assistant'),
            Message(role=Role.USER, content='Help me run an LLM in a lemon')
        ]
    )

    conversations = {
        '1__test_conversation_empty.json': conversation_empty.model_dump(),
        '2__test_conversation_full.json': conversation_full.model_dump(),
        '3__wrong_conversation_id.json': {'id': 3, 'name': 'wrong conversation id'}
    }

    for filename, conversation in conversations:
        with open(str(tmp_path / filename), 'w+', encoding='utf-8') as fp:
            json.dump(conversation, fp)

    with open(str(tmp_path / 'not_json_file'), 'w+', encoding='utf-8') as fp:
        fp.write('Hello World')


@mark.parametrize(
    'expected', {
        '1__test_conversation_empty.json': 1,
        '2__test_conversation_full.json': 2,
        '3__wrong_conversation_id.json': -1
    }
)
def test_from_json_parsing(tmp_path, expected):
    for path in tmp_path.iterdir():
        expected_id = expected[str(path)]
        conversation_id, conversation = Conversation.from_json(str(path))
        assert conversation_id == expected_id


@mark.parametrize('path_parameters', [
    {'path': 'not_exists', 'expected': -1},
    {'path': 'not_json_file', 'expected': -1}
])
def test_from_json_path(tmp_path, path_parameters):
    wrong_path = str(tmp_path / path_parameters['path'])
    conversation_id, conversation = Conversation.from_json(wrong_path)
    assert conversation_id == path_parameters['expected']
