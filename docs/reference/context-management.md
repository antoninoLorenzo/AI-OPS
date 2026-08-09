# Context Management

A session messages is an append-only record of everything that happened. The context given to the model each turn does not have to be that whole record. A `ContextView` sits between the two: it takes the full message list and returns a filtered, possibly compacted, copy to send to the model, without mutating the stored conversation.

Compacting the context is worthwhile for three reasons:

1. **Cost.** Fewer tokens per request, whether you pay per token or run your own model.
2. **Serving limits.** A self-hosted model's KV cache grows with the context; a smaller window keeps memory in check.
3. **Quality.** Models degrade when the context is crowded with stale detail.

## The `ContextView` protocol

```python
class ContextView(Protocol):
    def __call__(self, messages: list[Message]) -> list[Message]: ...
```

An implementation returns a deep copy of the messages it selects, so the stored conversation is never modified. Deep-copying is acceptable because messages are text only; it would need revisiting if binary blobs (base64 images, say) were introduced (unlikely).

Two implementations ship, registered under the names used in [`agent_config.json`](../configuration.md#agent)'s `context_view.kind`:

| `kind` | Implementation | Behavior |
|---|---|---|
| `raw` | `RawContextView` | Returns the full conversation unchanged (a deep copy). |
| `layered` | `LayeredContextView` | Heuristic compaction, described below. |

> The programmatic `AgentConfig` defaults to `RawContextView`; the API's `agent_config.json` defaults to `layered`.

Configure it per deployment:

```json
{ "context_view": { "kind": "layered", "params": { "max_window_tokens": 32768 } } }
```

or programmatically:

```python
from ai_ops.core.context_management import LayeredContextView
AgentConfig(context_fn=LayeredContextView(max_window_tokens=32768))
```

## LayeredContextView

`LayeredContextView` compacts at two levels of the trajectory. The system prompt and user messages are never dropped.

**Pre-checkpoint.** A `write_whiteboard` call is treated as a checkpoint: it means the agent finished a stretch of work and recorded the outcome (a finding, or a failed attempt). Everything before the last checkpoint is dropped, except user messages, which are kept. The idea is that the whiteboard entry now carries what mattered from that stretch, so the raw steps can go.

This is only as effective as how often the agent writes to the whiteboard, which depends on the model's instruction-following. When there is no checkpoint yet, nothing is dropped at this level.

**Active window.** Applied to what comes after the checkpoint, independently of whether the whiteboard is used at all:

- `think` calls beyond the most recent `max_think` are removed.
- `terminal` output longer than `truncation_threshold * max_window_tokens` is truncated (keeping the tail).
- `write_file` calls can be thinned the same way as `think`, but this is off unless a `file_write_alias` is configured (see the parameters below).

### Parameters

| Parameter | Default | Meaning |
|---|---|---|
| `max_window_tokens` | (required) | The model's usable context window. Drives the truncation budget. |
| `truncation_threshold` | `0.1` | Fraction of `max_window_tokens` above which a single `terminal` result is truncated. |
| `max_think` | `3` | Keep at most this many recent `think` calls in the active window. |
| `max_file_write` | `3` | Keep at most this many recent `write_file` calls (only applied when `file_write_alias` is set). |
| `terminal_alias` | `None` | Alternate tool name to treat as the terminal (for benchmark setups that rename it). Defaults to `terminal`. |
| `file_write_alias` | `None` | Tool name to treat as the file-write tool. Unset by default, so file-write thinning is off. |

`max_window_tokens` typically comes from the model's context length, set with `LLM_MAX_CONTEXT_LENGTH` when it can't be detected (see [Model Selection](../model_selection.md)).

> One consequence of pre-checkpoint compaction: keeping only user messages from an earlier stretch can leave two user messages adjacent in the context. A self-hosted model whose chat template rejects consecutive user messages will error, see [Model Selection](../model_selection.md#what-the-model-must-support).
