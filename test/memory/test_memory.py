# (missing) **test_load**
# - since it's done at initialization, IDK how to test
from pytest import fixture, mark

from src.core import Memory, Conversation, Role, Message


@fixture
def memory_instance():
    memory = Memory()
    print(f'Memory: {memory}')
    memory[1] = Conversation(
        conversation_id=1,
        name='test_save_conversation',
        messages=[
            Message(role=Role.SYS, content='You are an expert AI Assistant'),
            Message(role=Role.USER, content='Help me run an LLM in a lemon')
        ]
    )

    memory[2] = Conversation(
        conversation_id=2,
        name='test_delete_conversation',
        messages=[
            Message(role=Role.SYS, content='You are an expert AI Assistant'),
            Message(role=Role.USER, content='Help me run an LLM in a lemon')
        ]
    )

    yield memory


@mark.parametrize('parameters', [
    {'conversation_id': 'some', 'expected': False},
    {'conversation_id': 999, 'expected': False},
    {'conversation_id': 1, 'expected': True}
])
def test_save(
        memory_instance,
        tmp_path,
        monkeypatch,
        parameters
):
    monkeypatch.setattr(
        'src.core.memory.base.CONVERSATION_PATH',
        tmp_path
    )
    conversation_id = parameters['conversation_id']
    success = memory_instance.save(conversation_id)
    assert success == parameters['expected']

    if success:
        conversation_name = memory_instance[conversation_id].name
        conversation_path = str(
            tmp_path
            / f'{conversation_id}__{conversation_name}.json'
        )
        readable = Conversation.from_json(conversation_path)
        assert readable


@mark.parametrize('parameters', [
    {'conversation_id': 'some', 'expected': False},
    {'conversation_id': 999, 'expected': False},
    # conversation 1 is not persisted, but it should be removed from memory
    {'conversation_id': 2, 'expected': True, 'in_memory': False}
])
def test_delete(
        memory_instance,
        tmp_path,
        monkeypatch,
        parameters
):
    monkeypatch.setattr(
        'src.core.memory.base.CONVERSATION_PATH',
        tmp_path
    )

    conversation_id = parameters['conversation_id']
    success = memory_instance.delete(conversation_id)
    assert success == parameters['expected']

    if success:
        assert conversation_id not in memory_instance


