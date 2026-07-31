"""
Root fixtures shared by the whole suite.

Both the conversation store and the event store are module-global singletons
that `AgentRunner` reaches for directly (not through DI). They live for the
whole pytest process, so without a reset one test can leak a JSONL-backed store
into the next (e.g. after the API lifespan initialises the store with the JSONL
strategy). A JSONL `append` then raises because the on-disk conversation dir
doesn't exist for an in-memory conversation, breaking unrelated tests.

`_reset_global_stores` runs for every test and drops both singletons so the next
`get_*_store()` rebuilds a clean in-memory default.
"""
import pytest

import ai_ops.core.conversation as conversation_mod
import ai_ops.core.event_store as event_store_mod


@pytest.fixture(autouse=True)
def _reset_global_stores():
    conversation_mod._CONVERSATION_STORE = None
    event_store_mod._EVENT_STORE = None
    yield
    conversation_mod._CONVERSATION_STORE = None
    event_store_mod._EVENT_STORE = None
