# Run the API Server

This guide walks through configuring and launching the `ai_ops.api` HTTP server
from source with `uvicorn`. For the containerized deployment, see
[Getting Started](../getting-started.md#build-from-source). For the full
endpoint/schema/config listing, see the [API Reference](../reference/api.md).

The server is a FastAPI app (`ai_ops.api.api:app`) served with `uvicorn`. Both
ship as dependencies (the `api` group), so nothing extra to install.

## 1. Set the required configuration

At minimum the server needs a model. Point it at your LLM provider too, unless
that's baked into the model id.

```bash
# .env (loaded automatically) or your shell environment
AI_OPS_MODEL=hosted_vllm/gemma-3-27b-it        # required
LLM_API_BASE=https://your-vllm-domain/v1/      # provider base URL
LLM_API_KEY=your-provider-key                  # provider key
```

Everything else has a sensible default. See the
[configuration reference](../reference/api.md#configuration) for the full list.

## 2. Choose a bind host (and auth)

The server binds to `127.0.0.1` by default and, on localhost, will start without
an API key (it just logs a warning). That's fine for local development:

```bash
uvicorn ai_ops.api.api:app
# -> http://127.0.0.1:8000
```

> The app enforces the incoming `Host` header against `AI_OPS_HOST`
> (`TrustedHostMiddleware`), so keep `--host` and `AI_OPS_HOST` in agreement or
> requests get `400`.

### Exposing it beyond localhost

If you bind to anything other than localhost, an API key becomes **mandatory**:
the server refuses to boot without `AI_OPS_AUTH_TOKEN`. This is a deliberate
policy, never expose the agent on the network unauthenticated.

```bash
export AI_OPS_HOST=0.0.0.0
export AI_OPS_AUTH_TOKEN=$(openssl rand -hex 32)

uvicorn ai_ops.api.api:app --host 0.0.0.0 --port 8000
```

Clients must then send the token on every request:

```bash
curl -H "X-AI-OPS-ApiKey: $AI_OPS_AUTH_TOKEN" http://your-host:8000/health
```

## 3. (Optional) Tune the agent

The agent's tools, context strategy, temperature, and confirmation timeout come
from `agent_config.json` in the AI-OPS base directory (`~/.local/share/ai_ops/`).
Create it only if you want to override the defaults:

```json
{
  "tools": ["load_skill", "think", "write_whiteboard", "write_file", "terminal"],
  "context_view": { "kind": "layered", "params": { "max_window_tokens": 32768 } },
  "command_policies": [ { "kind": "allowlist", "params": { "allowlist": ["nmap", "ffuf"] } } ],
  "temperature": 0.4,
  "confirmation_timeout_s": 300
}
```

An unknown tool, context view, or policy name aborts startup with a non-zero
exit and a message naming the offender. Keys are documented in the
[reference](../reference/api.md#agent_configjson); tool and policy specifics live
in [Add a Tool](add-a-tool.md).

### Supplying config and skills

When you run from source, `agent_config.json` and `user_skills/` live directly in the base directory (`~/.local/share/ai_ops/`), so nothing special is needed.

When you run the API in a container, mount them into that directory instead:

```bash
docker run --rm -p 8000:8000 --env-file .env \
    --volume ai-ops-data:/home/aiops/.local/share/ai_ops \
    --mount type=bind,source=/path/to/agent_config.json,target=/home/aiops/.local/share/ai_ops/agent_config.json,readonly \
    --mount type=bind,source=/path/to/user_skills,target=/home/aiops/.local/share/ai_ops/user_skills,readonly \
    --cap-add=NET_RAW --cap-add=NET_ADMIN --security-opt=no-new-privileges \
    ai-ops:api-dev
```

The container runs as a non-root user, so the mounted paths must be world-readable: `644` for `agent_config.json`, `755` for the `user_skills/`
directories. Under SELinux, add `,relabel=shared` (or `,relabel=private`) to each `--mount`.

See [Add a Skill](add-a-skill.md) for the skill format and [Configuration](../configuration.md#agent) for every `agent_config.json` key.

## 4. Verify it's up

```bash
curl http://127.0.0.1:8000/health
# {"status":"ok"}

curl http://127.0.0.1:8000/model
# {"provider":"...","model_id":"...","max_context_length":32768, ...}
```

## 5. Drive a conversation

The typical client flow is to create a conversation, send a message, and read the
event stream:

```bash
# create a conversation, capture its short_id
SID=$(curl -s -X POST http://127.0.0.1:8000/conversation | jq .short_id)

# send a message; content and mode go in a JSON body.
# the response is newline-delimited JSON events
curl -N -X POST "http://127.0.0.1:8000/conversation/$SID" \
  -H "Content-Type: application/json" \
  -d '{"content": "enumerate the target", "mode": "supervised"}'
```

Each line is one event. In `supervised` mode, a `tool_call` with
`"requires_confirmation": true` means the agent is blocked waiting on you.
Approve or deny it with the same `call_id`:

```bash
curl -X POST "http://127.0.0.1:8000/conversation/$SID/confirmation/call-1?approved=true"
```

When you're done, stop or drop the agent:

```bash
curl -X POST   "http://127.0.0.1:8000/conversation/$SID/stop"   # halt, keep it
curl -X DELETE "http://127.0.0.1:8000/conversation/$SID"        # halt and drop
```

See the [API Reference](../reference/api.md) for every endpoint, event kind, and
error code.

## Notes on persistence

By default (`AI_OPS_STORAGE_STRATEGY=jsonl`) sessions are persisted under
`~/.local/share/ai_ops/sessions/`, so they survive a restart.
`GET /conversation/{short_id}` rebuilds a live agent for a stored session on
demand. Set `AI_OPS_STORAGE_STRATEGY=in_memory` to keep everything ephemeral.
