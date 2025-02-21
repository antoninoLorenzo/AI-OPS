from pytest import fixture, mark
from fastapi.testclient import TestClient

from src.api import app
from src.chat.service import get_agent
from src.core import Conversation
from test.mock.mock_agent import get_mock_agent


get_conversation_parameters = [
    {'conversation_id': 'not_id', 'expected_status': 422},
    {'conversation_id': -1, 'expected_status': 400},
    # uses conversation_context id (the right one basically)
    {'conversation_id': None, 'expected_status': 200}
]

rename_query_parameters = [
    {"query_parameters": {"not_param": ""}, 'expected_status': 422},
    {"query_parameters": {"new_name": ""}, 'expected_status': 400},
    {"query_parameters": {"new_name": "convo"}, 'expected_status': 200}
]

chat_query_parameters = [
    {'json_body': {'query': ''}, 'expected_status': 400},
    {'json_body': {'query': 10}, 'expected_status': 400},
    {'json_body': {'not_query': ''}, 'expected_status': 400}
]


# noinspection PyUnresolvedReferences
@fixture(scope="session", autouse=True)
def api_client():
    app.dependency_overrides[get_agent] = lambda: get_mock_agent()
    client = TestClient(app)
    yield client
    app.dependency_overrides.pop(get_agent)


@fixture(scope="session", autouse=True)
def conversation_context(api_client):
    conversation = api_client.post("/conversations", params={'name': 'test_convo'})
    yield conversation.json()


@mark.parametrize("parameters", get_conversation_parameters)
def test_get_conversation(
        api_client: TestClient,
        conversation_context: Conversation,
        parameters
):
    if parameters['conversation_id'] is None:
        conversation_id = conversation_context["conversation_id"]
    else:
        conversation_id = parameters['conversation_id']

    response = api_client.get(f'/conversations/{conversation_id}')
    assert response.status_code == parameters['expected_status']


@mark.parametrize("parameters", rename_query_parameters)
def test_rename_conversation(
        api_client: TestClient,
        conversation_context: Conversation,
        parameters
):
    conversation_id = conversation_context["conversation_id"]
    response = api_client.post(
        f"/conversations/{conversation_id}",
        params=parameters['query_parameters']
    )

    assert response.status_code == parameters['expected_status']

    if parameters['expected_status'] == 200:
        assert response.json()['name'] == parameters['query_parameters']['new_name']


@mark.parametrize(
    'parameters', [
        {'conversation_id': -1, 'expected_status': 400},
        {'conversation_id': None, 'expected_status': 200}
    ]
)
def test_save_conversation(
        api_client: TestClient,
        conversation_context: Conversation,
        tmp_path,
        monkeypatch,
        parameters
):
    monkeypatch.setattr(
        'src.core.memory.base.CONVERSATION_PATH',
        tmp_path
    )

    if parameters['conversation_id'] is None:
        conversation_id = conversation_context["conversation_id"]
    else:
        conversation_id = parameters['conversation_id']

    response = api_client.put(f"/conversations/{conversation_id}")
    assert response.status_code == parameters['expected_status']

    # check conversation format
    if parameters['expected_status'] == 200:
        saved_conversations = list(tmp_path.iterdir())
        assert saved_conversations
        for path in saved_conversations:
            convo = Conversation.from_json(str(path))
            assert convo is not (-1, None)


# noinspection PyPackageRequirements
@mark.parametrize("parameters", chat_query_parameters)
def test_query(
        api_client: TestClient,
        conversation_context: Conversation,
        parameters
):
    conversation_id = conversation_context["conversation_id"]
    with api_client.stream(
            method="POST",
            url=f"/conversations/{conversation_id}/chat",
            json=parameters['json_body']
    ) as response:
        assert response.status_code == parameters['expected_status']
