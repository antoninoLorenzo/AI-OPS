"""Regression test for the `aorchestrator` blocking-tool issue (ROADMAP).

`aorchestrator` runs synchronous tools via `asyncio.to_thread`, so a slow or
blocking tool executes off the event loop and doesn't freeze it — the API can
still service other conversations and the `/stop`/`/confirmation` endpoints
while a tool runs. This test pins that behaviour: it would fail if tool
execution went back to a plain `tool(args)` on the loop.
"""
import asyncio
import threading

from litellm import (
    ModelResponse,
    Choices,
    Usage,
    Function,
    ChatCompletionSystemMessage,
    ChatCompletionUserMessage,
    ChatCompletionMessageToolCall,
    Message as LiteLLMMessage,
)
from pydantic import BaseModel

import ai_ops.core.agent
import ai_ops.core.tracing
from ai_ops.core.agent import aorchestrator
from ai_ops.core.conversation import Message
from ai_ops.core.context_management import RawContextView
from ai_ops.core.llm import InferenceClient
from ai_ops.core.schema import AgentMode
from ai_ops.core.storage import Session
from ai_ops.core.tools.base import Tool

from test.core.mocks.llm import mock_aquery, mock_model


class _SlowIn(BaseModel):
    pass


class _SlowOut(BaseModel):
    released_in_time: bool


class SlowTool(Tool[_SlowIn, _SlowOut]):
    name = "slow_tool"
    description = "blocks until released by another coroutine, or times out"

    # generous upper bound: if the loop is responsive the releaser sets the
    # event far sooner; if the loop is frozen this is how long the run stalls.
    BLOCK_TIMEOUT_S = 2.0

    def __init__(self):
        self._release = threading.Event()
        self.released_in_time = None

    def release(self):
        self._release.set()

    def __call__(self, tool_args: _SlowIn) -> _SlowOut:
        # blocks the calling thread. If that's the event-loop thread, nobody can
        # call release() until this times out -> released_in_time is False.
        released = self._release.wait(timeout=self.BLOCK_TIMEOUT_S)
        self.released_in_time = released
        return _SlowOut(released_in_time=released)

    @staticmethod
    def format_result(tool_result: _SlowOut) -> str:
        return str(tool_result.released_in_time)


def _assistant_tool_call(call_id: str, name: str, arguments: str) -> ModelResponse:
    return ModelResponse(
        model="gpt-4o",
        choices=[Choices(
            finish_reason="tool_calls", index=0,
            message=LiteLLMMessage(role="assistant", content=None, tool_calls=[
                ChatCompletionMessageToolCall(
                    id=call_id, type="function",
                    function=Function(name=name, arguments=arguments)
                )
            ])
        )],
        usage=Usage(prompt_tokens=4, completion_tokens=4, total_tokens=8),
    )


def _assistant_stop() -> ModelResponse:
    return ModelResponse(
        model="gpt-4o",
        choices=[Choices(
            finish_reason="stop", index=0,
            message=LiteLLMMessage(role="assistant", content="done")
        )],
        usage=Usage(prompt_tokens=4, completion_tokens=4, total_tokens=8),
    )


class _SequencedChatCompletion:
    """Returns queued responses one per call (last one repeats)."""
    def __init__(self, responses):
        self._responses = responses
        self._i = 0

    def completion(self, model, stream: bool = False, **kwargs) -> ModelResponse:
        response = self._responses[min(self._i, len(self._responses) - 1)]
        self._i += 1
        return response

    async def acompletion(self, model, **kwargs) -> ModelResponse:
        return self.completion(model, **kwargs)


_MESSAGES = [
    Message(agent_id="react", message=ChatCompletionSystemMessage(role="system", content="sys")),
    Message(agent_id="react", message=ChatCompletionUserMessage(role="user", content="hi")),
]


async def test_blocking_tool_does_not_freeze_event_loop(monkeypatch):
    monkeypatch.setattr(ai_ops.core.tracing, "mlflow_ready", lambda: False)
    monkeypatch.setattr(ai_ops.core.agent, "aquery", mock_aquery)

    slow = SlowTool()
    client = InferenceClient(
        metadata=mock_model,
        client=_SequencedChatCompletion([
            _assistant_tool_call("c1", SlowTool.name, _SlowIn().model_dump_json()),
            _assistant_stop(),
        ]),
    )
    session = Session(uuid="conc", short_id=1, messages=_MESSAGES)

    async def releaser():
        # runs only if the loop is responsive while the tool is executing;
        # releases the tool well before BLOCK_TIMEOUT_S.
        await asyncio.sleep(0.05)
        slow.release()

    releaser_task = asyncio.create_task(releaser())
    _ = [
        event async for event in aorchestrator(
            client=client,
            session=session,
            tools={SlowTool.name: slow},
            context_fn=RawContextView(),
            mode=AgentMode.UNSUPERVISED,
            max_iterations=3,
        )
    ]
    await releaser_task

    # True only if releaser() got to run during tool execution -> loop was not
    # blocked by the synchronous tool call.
    assert slow.released_in_time is True
