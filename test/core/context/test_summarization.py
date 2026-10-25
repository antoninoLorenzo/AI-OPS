"""
Tests for `ai_ops.core.context._summary.SummarizationCompaction`.

The transform is stateful across turns: once the context crosses the threshold it
folds the trajectory into a summary, then reuses that summary on later turns
(appending only the new tail) and re-invokes the summarizer LLM *only* when the
view overflows again. State is recovered on resume from persisted `SummaryRecord`s.

The summarizer LLM is stubbed (`query`) so tests assert exactly when it is and
isn't called, without any network dependency.
"""
import pytest

import ai_ops.core.context._summary as summary_mod
import ai_ops.core.storage.session as session_mod
from ai_ops.core.context import SummarizationCompaction
from ai_ops.core.conversation import Message
from ai_ops.core.storage import get_session_store


class _FakeClient:
    model_id = "fake-model"


class _FakeUsage:
    prompt_tokens = 10
    completion_tokens = 5
    completion_tokens_details = None
    prompt_tokens_details = None


def _make_response(content: str):
    """Minimal stand-in for a litellm ModelResponse (what from_model_response reads)."""
    class _Msg:
        def model_dump(self):
            return {"role": "assistant", "content": content}

    class _Choice:
        message = _Msg()

    class _Resp:
        id = "resp-id"
        usage = _FakeUsage()
        choices = [_Choice()]

    return _Resp()


def _msg(role: str, content: str, tokens: int) -> Message:
    raw = {"role": role, "content": content}
    m = Message(agent_id="react", message=raw, token_count=tokens)
    return m


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Isolated JSONL store (singleton) + stubbed summarizer, returning a factory."""
    monkeypatch.setattr("ai_ops.core.storage.session.AI_OPS_BASE_DIR", tmp_path)
    (tmp_path / "sessions").mkdir()
    session_mod._SESSION_STORE = None

    calls = []

    def fake_query(client, messages, max_completion_tokens=None):
        calls.append({"messages": messages})
        return _make_response(f"SUMMARY-{len(calls)}")

    monkeypatch.setattr(summary_mod, "query", fake_query)

    store = get_session_store()

    def make(context_bound=100, context_threshold=1.0):
        session = store.create_session()
        transform = SummarizationCompaction(
            session_id=session.uuid,
            client=_FakeClient(),
            context_bound=context_bound,
            context_threshold=context_threshold,  # threshold tokens = bound * threshold
        )
        return transform, session.uuid

    return store, calls, make


def _sys_usr():
    return [_msg("system", "s", 5), _msg("user", "u", 5)]


def _roles(context):
    return [m.message["role"] for m in context]


def test_noop_below_threshold(env):
    _, calls, make = env
    transform, _ = make(context_bound=100, context_threshold=1.0)  # 100 token threshold

    messages = _sys_usr() + [_msg("assistant", "a", 10), _msg("user", "b", 10)]
    out = transform(messages)

    assert out is messages  # unchanged, no copy
    assert calls == []  # no LLM call


def test_first_overflow_summarizes_once(env):
    store, calls, make = env
    transform, sid = make(context_bound=100, context_threshold=1.0)

    messages = _sys_usr() + [_msg("assistant", f"a{i}", 10) for i in range(12)]  # 120 > 100
    out = transform(messages)

    assert len(calls) == 1
    assert _roles(out) == ["system", "user", "user"]  # sys, usr, summary
    assert out[2].message["content"] == "SUMMARY-1"
    assert transform._folded == len(messages)

    # persisted as a SummaryRecord with the fold boundary
    recs = store.get_session_by_uuid(sid).summarization_events
    assert len(recs) == 1 and recs[0].boundary == len(messages)


def test_reuse_summary_without_llm(env):
    _, calls, make = env
    transform, _ = make(context_bound=100, context_threshold=1.0)

    first = _sys_usr() + [_msg("assistant", f"a{i}", 10) for i in range(12)]
    transform(first)
    assert len(calls) == 1

    # a couple of small new messages appended -> reuse summary, append tail, no new call
    grown = first + [_msg("assistant", "n1", 5), _msg("user", "n2", 5)]
    out = transform(grown)

    assert len(calls) == 1  # NOT re-summarized
    assert _roles(out) == ["system", "user", "user", "assistant", "user"]
    assert out[2].message["content"] == "SUMMARY-1"
    assert out[3].message["content"] == "n1"


def test_refold_on_second_overflow(env):
    store, calls, make = env
    transform, sid = make(context_bound=100, context_threshold=1.0)

    first = _sys_usr() + [_msg("assistant", f"a{i}", 10) for i in range(12)]
    transform(first)
    grown = first + [_msg("assistant", f"b{i}", 10) for i in range(12)]  # tail now > threshold

    out = transform(grown)

    assert len(calls) == 2  # second summarization
    assert _roles(out) == ["system", "user", "user"]
    assert out[2].message["content"] == "SUMMARY-2"
    assert transform._folded == len(grown)

    # the refold is fed the previous summary, not the already-folded messages
    assert "<previous_summary>" in calls[1]["messages"][1]["content"]

    recs = store.get_session_by_uuid(sid).summarization_events
    assert [r.boundary for r in recs] == [len(first), len(grown)]


def test_state_recovered_on_resume(env):
    store, calls, make = env
    transform, sid = make(context_bound=100, context_threshold=1.0)

    first = _sys_usr() + [_msg("assistant", f"a{i}", 10) for i in range(12)]
    transform(first)
    assert len(calls) == 1

    # a fresh transform for the same session (new AgentRunner / resume) must pick up
    # the persisted summary + boundary instead of starting cold.
    resumed = SummarizationCompaction(
        session_id=sid, client=_FakeClient(),
        context_bound=100, context_threshold=1.0,
    )
    assert resumed._folded == len(first)
    assert resumed._summary_msg is not None
    assert resumed._summary_msg.message["content"] == "SUMMARY-1"

    # with no new messages since the fold it reuses the summary, still no extra call
    out = resumed(first)
    assert len(calls) == 1
    assert _roles(out) == ["system", "user", "user"]
