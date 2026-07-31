"""
Shared fixtures for the API test-suite.

The FastAPI app is built at *import* time (it reads settings, wires the auth
dependency and adds the TrustedHost middleware), so a few things have to be in
place before `ai_ops.api.api` is imported:

* `AI_OPS_MODEL` must be set (it's a required setting with no default).

Route handlers depend on state that is normally populated by the `lifespan`
(inference client, agent config, runner map). We don't run the lifespan for the
route tests; instead we inject those via `app.dependency_overrides`.

The conversation store is a module-global singleton and `AgentRunner` reaches
for it directly (not through DI), so `fresh_store` resets that singleton to a
clean in-memory store per test and the store dependency resolves to the very
same object.
"""
import os

# must run before importing the app (module-level construction reads settings).
os.environ.setdefault("AI_OPS_MODEL", "provider/model-id")

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

import ai_ops.core.conversation as conversation_mod
import ai_ops.core.event_store as event_store_mod
from ai_ops.core.conversation import ConversationStore, InMemoryConversationStore
from ai_ops.core.event_store import EventStore, InMemoryEventStore
from ai_ops.core.runner import AgentConfig

from ai_ops.api.api import (
    app,
    get_inference_client,
    get_runner_map,
    get_agent_config,
    get_event_store,
)

from test.core.mocks.llm import mock_inference_client
from test.core.mocks.tool import MockTool
# re-exported so tests in this package can request them as fixtures.
from test.core.mocks.tool import register_mock_tool, register_mock_confirm_tool  # noqa: F401


# TrustedHostMiddleware is configured with the settings host (127.0.0.1), so the
# client must send a matching Host header.
BASE_URL = "http://127.0.0.1"


@pytest.fixture
def fresh_store():
    """Reset the global conversation store to a clean in-memory instance."""
    store = ConversationStore(store_cls=InMemoryConversationStore)
    conversation_mod._CONVERSATION_STORE = store
    yield store
    conversation_mod._CONVERSATION_STORE = None


@pytest.fixture
def fresh_event_store():
    """Reset the global event store to a clean in-memory instance.

    `AgentRunner` grabs the singleton directly at construction, so route tests
    that stream events need this pointing at an in-memory store (a JSONL store
    would try to write to a non-existent on-disk conversation dir).
    """
    store = EventStore(store_cls=InMemoryEventStore)
    event_store_mod._EVENT_STORE = store
    yield store
    event_store_mod._EVENT_STORE = None


@pytest.fixture
def runner_map():
    """The map handed to the routes; tests can inspect it after a request."""
    return {}


@pytest.fixture
def agent_config():
    return AgentConfig(tools=[MockTool])


@pytest_asyncio.fixture
async def client(fresh_store, fresh_event_store, runner_map, agent_config):
    app.dependency_overrides[get_inference_client] = lambda: mock_inference_client
    app.dependency_overrides[get_runner_map] = lambda: runner_map
    app.dependency_overrides[get_agent_config] = lambda: agent_config
    app.dependency_overrides[get_event_store] = lambda: fresh_event_store

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as ac:
        yield ac

    app.dependency_overrides.clear()
