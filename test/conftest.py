"""
Root fixtures shared by the whole suite.

The session store is a module-global singleton that `AgentRunner` reaches for
directly (not through DI). It lives for the whole pytest process, so without a
reset one test can leak a store into the next (e.g. after the API lifespan
initialises the store with the JSONL strategy). A JSONL `append` then raises
because the on-disk session dir doesn't exist for an in-memory session,
breaking unrelated tests.

`get_session_store` defaults to the JSONL strategy (production default), so
resetting to `None` alone would make the next `get_session_store()` do disk i/o
against the real base dir. Instead `_reset_global_store` pins an in-memory
`SessionStore` for every test; tests that need a different strategy build their
own instance or reset the singleton explicitly.
"""
import pytest

import ai_ops.core.storage.session as session_mod
from ai_ops.core.storage import SessionStore, InMemorySessionStore


@pytest.fixture(autouse=True)
def _reset_global_store():
    session_mod._SESSION_STORE = SessionStore(store_cls=InMemorySessionStore)
    yield
    session_mod._SESSION_STORE = None
