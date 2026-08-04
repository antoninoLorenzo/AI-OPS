# AI-OPS Configuration

## API

The AI-OPS API is configured through the following environment variables:

| Variable | Type | Default | Required |
|---|---|---|---|
| `AI_OPS_HOST` | string | `127.0.0.1` | No | 
| `AI_OPS_AUTH_TOKEN` | string (secret) | - | No for localhost, Yes otherwise. |
| `AI_OPS_STORAGE_STRATEGY` | enum | `JSONL` | No | 
| `AI_OPS_MODEL` | string | - | Yes | 
| `LLM_API_BASE` | string | - | No | 
| `LLM_API_KEY` | string (secret) | - | No |


## CLI

The default CLI configuration is loaded from `~/.config/ai_ops/cli.json` if the file exists, however the flags have precedence over the file.
> Note: a missing file is not an error; a malformed file, or one that fails schema validation, is startup-fatal.

### Flags 

| Flag | Description |
|---|---|
| `--base-url <url>` | API base URL |
| `--api-key <key>` | API key, sent as `X-AI-OPS-ApiKey` on every request |
| `--mode <supervised\|unsupervised>` | Agent mode, set at startup only (no runtime toggle) |
| `--resume <short_id>` | Resume an existing conversation |

### Configuration File

```json
{
    "base_url": "<url>",
    "api_key": "<api_key>",
    "mode": "[supervised|unsupervised]",
    "resume": 1 or 0
}
```

## Agent

### Agent Settings

To configure the AI-OPS agent you can add `~/.local/share/ai_ops/agent_config.json`:

| Key | Type | Default |
|---|---|---|
| `tools` | list[str] | `DEFAULT_TOOLS` |
| `context_view.kind` | `raw` \| `layered` | `layered` |
| `context_view.params` | dict | `{max_window_tokens: LLM_MAX_CONTEXT_LENGTH or 8192}` |
| `command_policies` | list[{kind, params}] | `[]` |
| `temperature` | float | `0.4` |
| `prompt_extension` | string \| null | `null` |
| `confirmation_timeout_s` | float | `300.0` |


### Core Settings

| Variable | Type | Default | Notes |
|---|---|---|---|
| `LLM_MAX_CONTEXT_LENGTH` | int | `8192` | Also used as the default for `agent_config.json`'s `context_view.params.max_window_tokens` |
| `AI_OPS_OBSERVABILITY_BACKEND` | string | - | Only `mlflow` supported |
| `MLFLOW_TRACKING_URI` | string | - | Required if observability backend is `mlflow` |
| `MLFLOW_TRACKING_USERNAME` | string | - | Required by the MLflow server; not enforced in `_mlflow.py` |
| `MLFLOW_TRACKING_PASSWORD` | string (secret) | - | Required by the MLflow server; not enforced in `_mlflow.py` |
| `MLFLOW_EXPERIMENT_NAME` | string | - | Optional |
| `MLFLOW_TRACKING_INSECURE_TLS` | bool | `false` | Optional, not recommended |
| `AI_OPS_LOG_LEVEL` | string | - | Lowercase |
| `AI_OPS_LOG_FILE` | string (filename) | - | Created under `~/.local/share/ai_ops/` |
| `AI_OPS_LOG_STDOUT` | bool | - | `"true"` / `"false"` |
| `SKILL_VERIFY_INSTALLED` | bool | `false` | If `true`, checks each skill's `requirements` against `PATH` at startup and exits on any miss |

