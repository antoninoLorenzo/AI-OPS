"""
Challenging test-suite for `ai_ops.api`.

Layout:
* auth layer          -> `setup_auth` strategy binding, `_handle_api_key`, and an
                         end-to-end 401/200 check through the app dependency.
* app state / lifespan -> the `lifespan` populates `app.state`.
* routes               -> conversation lifecycle, streaming, stop/delete,
                         confirmation and usage, including the error branches.

Route tests drive the app through httpx `AsyncClient` + `ASGITransport` and mock
the inference / orchestration layer (`test.core.mocks`) so nothing hits a real
model. `pytest-asyncio` runs in auto mode, so async tests need no marker.
"""
import functools

import pytest
from pydantic import SecretStr, TypeAdapter
from fastapi import HTTPException

from litellm import ChatCompletionAssistantMessage

import ai_ops.core.runner
import ai_ops.api.auth as auth_mod
import ai_ops.api.api as api_mod
from ai_ops.api.api import get_event_store
from ai_ops.api.config import APISettings
from ai_ops.api.auth import _handle_api_key, _handle_no_op, setup_auth, API_KEY_NAME
from ai_ops.core.conversation import StorageStrategy, Message
from ai_ops.core.runner import AgentRunner, AgentConfig
from ai_ops.core.schema import AnyEvent, EventType, StopEvent, TextEvent
from ai_ops.core.agent import AgentMode

from test.core.mocks.llm import mock_inference_client
from test.core.mocks.agent import mock_aorchestrator
from test.core.mocks.tool import MockTool


_event_adapter = TypeAdapter(AnyEvent)


def _settings(host="127.0.0.1", auth_token=None):
    return APISettings(
        host=host,
        auth_token=auth_token,
        storage_strategy=StorageStrategy.IN_MEMORY,
        model="provider/model-id",
        llm_provider_base="https://testprovider-not-exists",
        llm_provider_key=None,
    )


async def _create_conversation(client) -> int:
    """POST /conversation and return its short_id."""
    resp = await client.post("/conversation")
    assert resp.status_code == 200, resp.text
    return resp.json()["short_id"]


# =============================================================================
# Auth layer
# =============================================================================

# setup_auth picks the dependency implementation from (host, auth_token):
#   token set                      -> real check (`_handle_api_key`)
#   no token + localhost           -> permissive no-op (`_handle_no_op`)
#   no token + exposed on network  -> refuse to boot (`SystemExit`)
_SETUP_AUTH_CASES = [
    {"host": "127.0.0.1", "auth_token": SecretStr("secret"), "expected": _handle_api_key},
    {"host": "localhost", "auth_token": SecretStr("secret"), "expected": _handle_api_key},
    {"host": "0.0.0.0",   "auth_token": SecretStr("secret"), "expected": _handle_api_key},
    {"host": "127.0.0.1", "auth_token": None, "expected": _handle_no_op},
    {"host": "localhost", "auth_token": None, "expected": _handle_no_op},
    {"host": "0.0.0.0",   "auth_token": None, "expected": SystemExit},
    {"host": "10.0.0.5",  "auth_token": None, "expected": SystemExit},
]


@pytest.mark.parametrize("test_case", _SETUP_AUTH_CASES)
def test_setup_auth_binding(test_case, monkeypatch):
    monkeypatch.setattr(auth_mod, "get_settings",
                        lambda: _settings(test_case["host"], test_case["auth_token"]))
    # start from a clean slate so we assert on what setup_auth binds.
    monkeypatch.setattr(auth_mod, "handle_api_key", None)

    if test_case["expected"] is SystemExit:
        with pytest.raises(SystemExit):
            setup_auth()
    else:
        setup_auth()
        assert auth_mod.handle_api_key is test_case["expected"]


# _handle_api_key compares the provided key against the configured token.
_HANDLE_KEY_CASES = [
    {"token": "secret", "provided": "secret", "raises": False},
    {"token": "secret", "provided": "wrong",  "raises": True},
    {"token": "secret", "provided": None,     "raises": True},   # missing header
    {"token": "secret", "provided": "",       "raises": True},
]


@pytest.mark.parametrize("test_case", _HANDLE_KEY_CASES)
async def test_handle_api_key(test_case, monkeypatch):
    monkeypatch.setattr(auth_mod, "get_settings",
                        lambda: _settings(auth_token=SecretStr(test_case["token"])))

    if test_case["raises"]:
        with pytest.raises(HTTPException) as exc:
            await _handle_api_key(req=None, api_key=test_case["provided"])
        assert exc.value.status_code == 401
    else:
        assert await _handle_api_key(req=None, api_key=test_case["provided"]) is None


# End-to-end: force the app's auth dependency to the real check and verify the
# 401/200 outcome actually reaches the client through the dependency chain.
_AUTH_HTTP_CASES = [
    {"header": {API_KEY_NAME: "secret"}, "status": 200},
    {"header": {API_KEY_NAME: "wrong"},  "status": 401},
    {"header": {},                       "status": 401},
]


@pytest.mark.parametrize("test_case", _AUTH_HTTP_CASES)
async def test_auth_dependency_enforced(test_case, client, monkeypatch):
    monkeypatch.setattr(auth_mod, "get_settings",
                        lambda: _settings(auth_token=SecretStr("secret")))
    # the app captured `Depends(handle_api_key)` at import; override that object.
    api_mod.app.dependency_overrides[api_mod.handle_api_key] = _handle_api_key

    resp = await client.post("/conversation", headers=test_case["header"])
    assert resp.status_code == test_case["status"], resp.text


# =============================================================================
# App state / lifespan
# =============================================================================

async def test_lifespan_populates_state(monkeypatch):
    sentinel_config = AgentConfig(tools=[MockTool])
    recorded = {}

    monkeypatch.setattr(api_mod, "build_inference_client", lambda config: mock_inference_client)
    monkeypatch.setattr(api_mod, "build_agent_config", lambda: sentinel_config)
    monkeypatch.setattr(api_mod, "_core_get_conversation_store",
                        lambda strategy=None: recorded.setdefault("conversation_strategy", strategy))
    monkeypatch.setattr(api_mod, "_core_get_event_store",
                        lambda strategy=None: recorded.setdefault("event_strategy", strategy))

    # a throwaway app object so we don't clobber the imported one's state.
    from fastapi import FastAPI
    dummy = FastAPI()

    async with api_mod.lifespan(dummy):
        assert dummy.state.inference_client is mock_inference_client
        assert dummy.state.agent_config is sentinel_config
        assert isinstance(dummy.state.runner_map, dict)

    # both stores initialised once with the configured strategy (default JSONL).
    strategy = api_mod.get_settings().storage_strategy
    assert recorded["conversation_strategy"] == strategy
    assert recorded["event_strategy"] == strategy


# =============================================================================
# POST /conversation
# =============================================================================

async def test_create_conversation(client, runner_map):
    resp = await client.post("/conversation")
    assert resp.status_code == 200, resp.text

    body = resp.json()
    assert body["uuid"]
    short_id = body["short_id"]

    # a runner was registered under the short_id and it was seeded as a new
    # conversation (system prompt appended -> at least one message).
    assert short_id in runner_map
    assert isinstance(runner_map[short_id], AgentRunner)
    assert len(body["messages"]) >= 1
    assert body["messages"][0]["message"]["role"] == "system"


# =============================================================================
# GET /conversation/{short_id}
# =============================================================================

async def test_load_conversation_existing(client):
    short_id = await _create_conversation(client)
    resp = await client.get(f"/conversation/{short_id}")
    assert resp.status_code == 200, resp.text
    # the route now returns the persisted event list, not the conversation.
    # a freshly created conversation has produced no events yet.
    assert resp.json() == []


async def test_load_conversation_returns_persisted_events(
    client, runner_map, monkeypatch, register_mock_tool
):
    # run an agent so events get persisted, then load them back.
    short_id = await _create_conversation(client)

    events = [
        Message(message=ChatCompletionAssistantMessage(role="assistant", content="hello")),
        StopEvent(issuer="agent", reason="done"),
    ]
    monkeypatch.setattr(
        ai_ops.core.runner, "aorchestrator",
        functools.partial(mock_aorchestrator, mock_events=events),
    )

    resp = await client.post(f"/conversation/{short_id}", json={"content": "hi", "mode": "supervised"})
    assert resp.status_code == 200, resp.text
    # drain the stream so the runner finishes and everything is persisted.
    _ = resp.text

    resp = await client.get(f"/conversation/{short_id}")
    assert resp.status_code == 200, resp.text

    parsed = [_event_adapter.validate_python(e) for e in resp.json()]
    kinds = [p.kind for p in parsed]
    # the user turn is persisted first, then the assistant text and the stop.
    assert kinds == [EventType.USER_MESSAGE, EventType.TEXT, EventType.STOP]
    assert parsed[0].content == "hi"
    assert isinstance(parsed[1], TextEvent) and parsed[1].chunk == "hello"


async def test_load_conversation_malformed_events_returns_500(client, runner_map):
    # a malformed on-disk event list surfaces as RuntimeError from the store,
    # which the route maps to 500. The client fixture clears the override on teardown.
    short_id = await _create_conversation(client)

    class _RaisingEventStore:
        def get_by_conversation_uuid(self, conversation_id):
            raise RuntimeError("malformed event list")

    api_mod.app.dependency_overrides[get_event_store] = lambda: _RaisingEventStore()

    resp = await client.get(f"/conversation/{short_id}")
    assert resp.status_code == 500, resp.text


async def test_load_conversation_rehydrates_runner(client, runner_map):
    short_id = await _create_conversation(client)
    # simulate a restarted server: the conversation persists but no live runner.
    runner_map.pop(short_id)

    resp = await client.get(f"/conversation/{short_id}")
    assert resp.status_code == 200, resp.text
    # loading rebuilt a runner for the existing conversation.
    assert short_id in runner_map
    assert isinstance(runner_map[short_id], AgentRunner)


async def test_load_conversation_unknown_returns_404(client):
    resp = await client.get("/conversation/999")
    assert resp.status_code == 404, resp.text


# =============================================================================
# POST /conversation/{short_id} (start_agent, JSONL stream)
# =============================================================================

async def test_start_agent_streams_events(client, runner_map, monkeypatch, register_mock_tool):
    short_id = await _create_conversation(client)

    events = [
        Message(message=ChatCompletionAssistantMessage(role="assistant", content="hello")),
        StopEvent(issuer="agent", reason="done"),
    ]
    monkeypatch.setattr(
        ai_ops.core.runner, "aorchestrator",
        functools.partial(mock_aorchestrator, mock_events=events),
    )

    resp = await client.post(f"/conversation/{short_id}", json={"content": "hi", "mode": "supervised"})
    assert resp.status_code == 200, resp.text

    lines = [ln for ln in resp.text.splitlines() if ln.strip()]
    parsed = [_event_adapter.validate_json(ln) for ln in lines]

    # the assistant Message became a TextEvent; the StopEvent passed through.
    # crucially, every serialized event carries its `kind` tag on the wire.
    kinds = [p.kind for p in parsed]
    assert kinds == [EventType.TEXT, EventType.STOP]
    assert isinstance(parsed[0], TextEvent) and parsed[0].chunk == "hello"


async def test_start_agent_missing_runner_returns_404(client):
    resp = await client.post("/conversation/999", json={"content": "hi", "mode": "supervised"})
    assert resp.status_code == 404, resp.text


async def test_start_agent_already_running_returns_400(client, runner_map):
    short_id = await _create_conversation(client)
    # the guard is checked synchronously inside `arun`, before the stream starts.
    runner_map[short_id]._running = True

    resp = await client.post(f"/conversation/{short_id}", json={"content": "hi", "mode": "supervised"})
    assert resp.status_code == 400, resp.text


async def test_start_agent_invalid_conversation_returns_500(client, fresh_store, runner_map, agent_config):
    # a conversation with no system message: after `arun` appends the user turn
    # the list is [user] only, which fails `is_valid_message_list` -> ValueError.
    conv = fresh_store.create()
    runner = AgentRunner(
        conversation_id=conv.uuid,
        client=mock_inference_client,
        config=agent_config,
        is_new_conversation=False,
    )
    runner_map[conv.short_id] = runner

    resp = await client.post(f"/conversation/{conv.short_id}", json={"content": "hi", "mode": "supervised"})
    assert resp.status_code == 500, resp.text


# =============================================================================
# POST /conversation/{short_id}/send
# =============================================================================

async def test_send_enqueues_when_running(client, runner_map):
    short_id = await _create_conversation(client)
    # send only accepts while a run is in flight and no message is pending.
    runner_map[short_id]._running = True

    resp = await client.post(f"/conversation/{short_id}/send", json={"content": "hi"})
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"enqueued": True}
    assert runner_map[short_id]._pending_message is not None


async def test_send_conflict_when_not_running(client, runner_map):
    short_id = await _create_conversation(client)
    # runner is idle (_running is False) -> send returns False -> 409.
    resp = await client.post(f"/conversation/{short_id}/send", json={"content": "hi"})
    assert resp.status_code == 409, resp.text


async def test_send_missing_runner_returns_404(client):
    resp = await client.post("/conversation/999/send", json={"content": "hi"})
    assert resp.status_code == 404, resp.text


# =============================================================================
# DELETE /conversation/{short_id}
# =============================================================================

async def test_delete_idle_runner(client, runner_map):
    short_id = await _create_conversation(client)
    resp = await client.delete(f"/conversation/{short_id}")
    assert resp.status_code == 200, resp.text
    assert short_id not in runner_map


async def test_delete_running_runner_stops_and_removes(client, runner_map):
    short_id = await _create_conversation(client)
    runner = runner_map[short_id]
    runner._running = True

    resp = await client.delete(f"/conversation/{short_id}")
    assert resp.status_code == 200, resp.text
    assert runner._user_stopped is True   # stop() was invoked
    assert short_id not in runner_map


async def test_delete_missing_runner_returns_404(client):
    resp = await client.delete("/conversation/999")
    assert resp.status_code == 404, resp.text


# =============================================================================
# POST /conversation/{short_id}/stop
# =============================================================================

async def test_stop_running_runner(client, runner_map):
    short_id = await _create_conversation(client)
    runner = runner_map[short_id]
    runner._running = True

    resp = await client.post(f"/conversation/{short_id}/stop")
    assert resp.status_code == 200, resp.text
    assert runner._user_stopped is True
    # stop does not remove the runner (unlike delete).
    assert short_id in runner_map


async def test_stop_idle_runner_is_noop(client, runner_map):
    short_id = await _create_conversation(client)
    resp = await client.post(f"/conversation/{short_id}/stop")
    assert resp.status_code == 200, resp.text
    assert runner_map[short_id]._user_stopped is False


async def test_stop_missing_runner_returns_404(client):
    resp = await client.post("/conversation/999/stop")
    assert resp.status_code == 404, resp.text


# =============================================================================
# POST /conversation/{short_id}/confirmation/{tool_call_id}
# =============================================================================

async def test_confirm_pending_call(client, runner_map):
    short_id = await _create_conversation(client)
    runner = runner_map[short_id]
    runner._blocked_calls.append("call-1")

    resp = await client.post(f"/conversation/{short_id}/confirmation/call-1", params={"approved": True})
    assert resp.status_code == 200, resp.text


async def test_confirm_unknown_call_returns_400(client, runner_map):
    short_id = await _create_conversation(client)
    resp = await client.post(f"/conversation/{short_id}/confirmation/nope", params={"approved": True})
    assert resp.status_code == 400, resp.text


async def test_confirm_missing_runner_returns_404(client):
    resp = await client.post("/conversation/999/confirmation/call-1", params={"approved": True})
    assert resp.status_code == 404, resp.text


# =============================================================================
# GET /conversation/{short_id}/usage
# =============================================================================

async def test_usage_reports_tokens(client, fresh_store):
    short_id = await _create_conversation(client)

    resp = await client.get(f"/conversation/{short_id}/usage")
    assert resp.status_code == 200, resp.text

    body = resp.json()
    conv = fresh_store.get_by_short_id(short_id)
    expected = sum(m.token_count for m in conv.messages if m.token_count is not None)
    assert body["total_tokens"] == expected
    assert body["max_context_length"] == mock_inference_client.metadata.max_context_length


async def test_usage_unknown_returns_404(client):
    resp = await client.get("/conversation/999/usage")
    assert resp.status_code == 404, resp.text
