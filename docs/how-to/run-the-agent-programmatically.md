# How to Run the AI-OPS Agent Programmatically

You can execute the AI-OPS Agent programmatically. The Agent is driven by the `AgentRunner` (`ai_ops.core.runner`) class that isolates the concrete agent `orchestrator`/`aorchestrator` implementation (`ai_ops.core.agent`).

There are both sync and async paths, for general use stick to the asynchronous version (that's what the api uses). For other use cases (ex. benchmarks, prompt optimization) you may want to use the [Synchronous Execution Model](#synchronous-execution-model).

The `AgentRunner` needs a pre-existing session and an already configured `InferenceClient`. 

**Create an `InferenceClient`**
```python
from ai_ops.core.llm import ModelConfig, build_inference_client

# under the hood InferenceClient uses litellm.Router
agent_model = ModelConfig(
    model="hosted_vllm/gemma4-31B-it-AWQ",
    api_base="https://your-vllm-domain/v1/", # optional
    api_key="you-should-have-one",           # optional
)
llm_client = build_inference_client(config=agent_model)
```

**Create a session**
```python
from ai_ops.core.storage import get_session_store

session_store = get_session_store()
session = session_store.create_session()
```

**Configure the `AgentRunner`**
```python
from ai_ops.core.runner import AgentRunner, AgentConfig
from ai_ops.core.tools import DEFAULT_TOOLS
from ai_ops.core.tools.terminal import AllowListPolicy
from ai_ops.core.context_management import LayeredContextView

agent = AgentRunner(
    session_id=session.uuid,
    client=llm_client,
    config=AgentConfig(
        tools=DEFAULT_TOOLS,
        context_fn=LayeredContextView(max_window_tokens=32768),
        working_directory="/tmp/ai_ops/",
        command_policies=(AllowListPolicy(allowlist=["nmap", "ffuf", "..."]),),
        temperature=0.4,             # default is AI_OPS_AGENT_TEMPERATURE / 0.4
        prompt_extension=None,       # optional string appended to the system prompt
        confirmation_timeout_s=300,  # default; a pending call is denied on timeout
    ),
    is_new_conversation=True,        # default; writes the system prompt as the first message
    extra_tool_ctx=None,             # optional dict passed to ToolContext.extra
)
```
> `is_new_conversation=False` skips writing the system prompt (used to resume a conversation).

**Consume the Event Stream**

```python
import asyncio
from ai_ops.core.schema import (
    UserMessageEvent, AgentMode,
    ReasoningEvent, TextEvent, ToolCallEvent, ToolConfirmationEvent,
    ToolResultEvent, ToolErrorEvent, StopEvent,
)

async def main():
    event_stream = agent.arun(
        user_message=UserMessageEvent(content="say deez"),
        mode=AgentMode.SUPERVISED,   # default; UNSUPERVISED raises the iteration cap
        max_iterations=None,         # defaults to 30 (SUPERVISED) / 60 (UNSUPERVISED)
    )

    async for event in event_stream:
        if isinstance(event, ReasoningEvent):
            print(f"<think>{event.chunk}</think>", end="")
        elif isinstance(event, TextEvent):
            print(f"Assistant: {event.chunk}", end="")
        elif isinstance(event, ToolCallEvent):
            print(f"\n[Tool Call] {event.name}({event.args})")
            if event.requires_confirmation:
                approved = input(f"Allow {event.name}? [y/N] ").strip().lower() == "y"
                agent.confirm(ToolConfirmationEvent(call_id=event.call_id, approved=approved))
        elif isinstance(event, ToolResultEvent):
            print(f"[Tool Result] {event.name} -> {event.result}")
        elif isinstance(event, ToolErrorEvent):
            print(f"[Tool Error] {event.name} ({event.failure}): {event.error}")
        elif isinstance(event, StopEvent):
            if event.error:
                print(f"\n[Fatal Error] {event.error}")
            else:
                print(f"\n[Execution Stopped] Reason: {event.reason}")

asyncio.run(main())
```

`arun()` raises `RuntimeError` if the runner is already running, and `ValueError` if the persisted conversation isn't a valid `[system, user, ...]` message list.

> Note: `ToolCallEvent.requires_confirmation` is only set in the async path.

### Multi-turn and Interruption

```python
agent.send(UserMessageEvent(content="follow-up message"))  # queue next user turn
agent.stop()                                               # non-preemptive stop
```
 
- **`send()` only has an effect while `arun()` is actively running**, it checks an internal flag that only the async path sets. Calling it before starting, after a stop, or during a sync `run()` call returns `False`.
- It returns `True` if the message was queued, `False` otherwise (e.g. a message was already pending). Check the return value if you need to know whether it landed.
- The queued message isn't necessarily held until the very end of the turn: it's spliced in as soon as there are no pending tool calls, which can happen right after any tool-call-free assistant message, not only after a `StopEvent`.
- `stop()` flags the runner to stop after the current event finishes (e.g. an in-flight tool call completes).

## Synchronous Execution Model

A synchronous `AgentRunner.run` also exists, however:
- It never evaluates command policy or confirmation (`requires_confirmation` is never true).
- It doesn't append events to the session, only messages are persisted, not the structured event stream. If you need `events.jsonl` for a session, drive it through `arun()`.
- `send()` will never successfully queue a message against a sync run. `stop()` still works, since it flips a flag shared by both paths.
> Note: I may want to change some of this behaviour (specifically event persistence and send) but it's not currently a priority.