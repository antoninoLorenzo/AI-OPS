# API Reference

The server is a FastAPI app (`ai_ops.api.api:app`) that wraps `ai_ops.core`, exposing one agent per conversation.
For the steps to configure and launch it, see the how-to: [Run the API Server](../how-to/run-the-api-server.md).

---

## Authentication

Authentication uses a single token provided by the user with `AI_OPS_AUTH_TOKEN` environment variable, clients set it in the header `X-AI-OPS-ApiKey: <token>`. The token is **opt-in only when the API is bound to localhost** (`127.0.0.1` or `localhost`), if the app is bound to any other host the token is always required. 

Also note that *every route* requires the token to be set.


### Host header

`TrustedHostMiddleware` is configured with the `host` setting, so requests must carry a `Host` header matching `AI_OPS_HOST`. A mismatch returns
`400 Bad Request` before any route runs.

---

## Endpoints

### Health & model

| Method | Path | Success | Body |
|---|---|---|---|
| `GET` | `/health` | `200` | `{"status": "ok"}` |
| `GET` | `/model` | `200` | [`ModelMetadata`](#modelmetadata) |

### Conversation lifecycle

| Method | Path | Success | Errors | Purpose |
|---|---|---|---|---|
| `POST` | `/conversation` | `200` | — | Create a conversation and its agent. |
| `GET` | `/conversation/{short_id}` | `200` | `404` | Load a conversation (rehydrates the agent if needed). |
| `POST` | `/conversation/{short_id}` | `200` (stream) | `400`, `404`, `500` | Send a user message and stream the agent's events. |
| `POST` | `/conversation/{short_id}/stop` | `200` | `404` | Stop a running agent, keep it registered. |
| `DELETE` | `/conversation/{short_id}` | `200` | `404` | Stop (if running) and drop the agent. |
| `POST` | `/conversation/{short_id}/confirmation/{tool_call_id}` | `200` | `400`, `404` | Approve/deny a pending tool call. |
| `GET` | `/conversation/{short_id}/usage` | `200` | `404` | Token usage for the conversation. |

`short_id` is the small human-friendly integer returned by
`POST /conversation` — not the `uuid`.

---

### `POST /conversation`

Creates a new conversation, seeds it with the system prompt, and constructs the
backing `AgentRunner` (registered in-memory under `short_id`).

**Response `200`** — a [`Conversation`](#conversation). `messages` already
contains at least the `system` message.

```json
{
  "uuid": "6f1e...-...",
  "short_id": 1,
  "messages": [ { "message": { "role": "system", "content": "..." }, "token_count": 812 } ]
}
```

---

### `GET /conversation/{short_id}`

Returns the stored [`Conversation`](#conversation). If no live `AgentRunner`
exists for it (e.g. after a server restart, with a persistent store), one is
rebuilt from the stored conversation before returning.

- **`200`** — the conversation.
- **`404`** — no conversation with that `short_id`.

---

### `POST /conversation/{short_id}`

Sends a user message and streams the agent's response. This is the only
streaming endpoint.

**Query parameters**

| Name | Type | Description |
|---|---|---|
| `content` | `string` | The user message text. |
| `mode` | `supervised` \| `unsupervised` | Agent run mode. `supervised` gates sensitive tool calls behind confirmation; `unsupervised` skips gated calls without asking and raises the iteration cap. |

**Response `200`** — `application/x-ndjson`. One JSON [event](#events) per line,
each tagged with a `kind` field; read line by line until a `stop` event.

```
{"kind":"reasoning","chunk":"let me check the host..."}
{"kind":"text","chunk":"Scanning","stream":false,"stream_done":false}
{"kind":"tool_call","call_id":"call-1","name":"terminal","args":{...},"requires_confirmation":true}
{"kind":"tool_result","call_id":"call-1","name":"terminal","args":{...},"result":{...}}
{"kind":"stop","issuer":"agent","reason":"done","max_iteration":false,"error":null}
```

**Errors** — surfaced as status codes *before* the stream starts:

| Status | Meaning |
|---|---|
| `404` | No agent registered for `short_id`. |
| `400` | The agent is already running for this conversation. |
| `500` | The conversation is not a valid message list (internal error in conversation management). |

When a streamed `tool_call` has `requires_confirmation: true`, the agent is
blocked awaiting your decision — reply with
[`POST .../confirmation/{tool_call_id}`](#post-conversationshort_idconfirmationtool_call_id)
carrying the same `call_id`. The wait is bounded by `confirmation_timeout_s`
(see [`agent_config.json`](#agent_configjson)); on timeout the call is treated as
denied and flows back to the model as a normal `tool_result`.

---

### `POST /conversation/{short_id}/stop`

Requests a non-preemptive stop. If the agent is running, `stop()` is issued (it
finishes the in-flight event before halting); if idle, this is a no-op. The
agent stays registered and can be sent another message.

- **`200`** — accepted. **`404`** — no agent for `short_id`.

### `DELETE /conversation/{short_id}`

Same stop semantics as above, then the agent is removed from the registry.
Intended for client shutdown/exit.

- **`200`** — removed. **`404`** — no agent for `short_id`.

### `POST /conversation/{short_id}/confirmation/{tool_call_id}`

Delivers the user's decision for a pending tool call (one previously streamed
with `requires_confirmation: true`).

**Query parameters**

| Name | Type | Description |
|---|---|---|
| `approved` | `bool` | `true` runs the call, `false` blocks it. |

- **`200`** — decision recorded.
- **`400`** — `tool_call_id` doesn't match any pending call.
- **`404`** — no agent for `short_id`.

### `GET /conversation/{short_id}/usage`

Sums `token_count` across the conversation's messages and reports it alongside
the model's context window.

**Response `200`**

```json
{ "total_tokens": 4211, "max_context_length": 32768 }
```

- **`404`** — no conversation with that `short_id`.

---

## Schemas

### Conversation

`ai_ops.core.conversation.Conversation`

| Field | Type | Description |
|---|---|---|
| `uuid` | `string` | Stable conversation identifier. |
| `short_id` | `int` | Human-friendly id used in all route paths. |
| `messages` | `Message[]` | Ordered message list. |

Each `Message` carries the raw provider `message` object (`role`, `content`,
tool calls, …) and an optional `token_count`.

### ModelMetadata

`ai_ops.core.llm.ModelMetadata`

| Field | Type |
|---|---|
| `provider` | `string` |
| `model_id` | `string` |
| `max_context_length` | `int` |
| `tool_use` | `bool` |
| `reasoning` | `bool` |
| `response_format` | `bool` |
| `structured_output` | `bool` |

### Events

Streamed by `POST /conversation/{short_id}`. All events share a `kind`
discriminator (`ai_ops.core.schema.AnyEvent`). Fields below are the wire fields
per `kind`.

| `kind` | Fields | Meaning |
|---|---|---|
| `text` | `chunk`, `stream`, `stream_done` | Assistant text. |
| `reasoning` | `chunk` | Model reasoning/thinking. |
| `tool_call` | `call_id`, `name`, `args`, `requires_confirmation` | The agent is invoking a tool. `requires_confirmation: true` means it's blocked awaiting your decision. |
| `tool_result` | `call_id`, `name`, `args`, `result` | A tool returned. A denied/timed-out call also arrives here (its `not_admitted_result`). |
| `tool_error` | `failure` (`validation_error`\|`execution_error`), `tool_call_id`, `name`, `error` | A tool raised. |
| `stop` | `issuer` (`agent`\|`user`), `reason`, `max_iteration`, `error` | Terminal event. `error` is set on a fatal error. |

`tool_confirmation` (`call_id`, `approved`) and `user_message` (`content`) also
exist in the union but are *inputs* to the runner, not things you'll read off
the stream. Over HTTP you supply them via the confirmation endpoint and the
`content` query parameter respectively.

---

## Configuration

Configuration is read once at startup from environment variables (`APISettings`,
prefix `AI_OPS_`) plus a JSON file for the agent. Variables without the
`AI_OPS_` prefix are shared with `ai_ops.core`.

### Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `AI_OPS_MODEL` | **yes** | — | Fully-qualified model id (e.g. `hosted_vllm/gemma-...`). |
| `AI_OPS_HOST` | no | `127.0.0.1` | Bind host; also enforced as the expected `Host` header. |
| `AI_OPS_AUTH_TOKEN` | conditional | unset | API key clients must send. Mandatory when not bound to localhost (see [Auth policy](#auth-policy)). |
| `AI_OPS_STORAGE_STRATEGY` | no | `jsonl` | Conversation store backend (`jsonl` \| `in_memory`). |
| `LLM_API_BASE` | no | — | LLM provider base URL. |
| `LLM_API_KEY` | no | — | LLM provider key. |
| `LLM_MAX_CONTEXT_LENGTH` | no | `8192` | Default context window for the layered context view. |

> The server calls `load_dotenv()` at import, so a `.env` file is honoured.

### `agent_config.json`

The agent itself is configured from `agent_config.json` in the AI-OPS base
directory (`~/.local/share/ai_ops/`). `build_agent_config()` reads it into an
`AgentConfig`; an invalid tool/context-view/policy name aborts startup with a
non-zero exit.

| Key | Type | Default | Description |
|---|---|---|---|
| `tools` | `string[]` | all `DEFAULT_TOOLS` | Tool names to enable (must be registered). |
| `context_view` | `{kind, params}` | `layered`, `max_window_tokens` from `LLM_MAX_CONTEXT_LENGTH` | Context compaction strategy (`raw` \| `layered`). |
| `command_policies` | `{kind, params}[]` | `[]` | Terminal admission policies, evaluated in order. |
| `temperature` | `float` | `0.4` | Sampling temperature (takes precedence over `AI_OPS_AGENT_TEMPERATURE`). |
| `prompt_extension` | `string \| null` | `null` | Appended to the system prompt. |
| `confirmation_timeout_s` | `float` | `300.0` | Seconds to wait on a tool confirmation before denying it. |

See [Add a Tool](../how-to/add-a-tool.md) for tool names and policy details, and
`docs/notes.md` for the conversation store and context-view internals.

### Auth policy

`setup_auth()` binds one of three behaviours at startup from `(host, auth_token)`:

| Host | `AI_OPS_AUTH_TOKEN` | Result |
|---|---|---|
| localhost | set | API-key check enforced |
| localhost | unset | no-op auth (warning logged) |
| non-local | set | API-key check enforced |
| non-local | unset | **refuses to boot** (`SystemExit`) |

The rule: never expose the API on the network without a token.
