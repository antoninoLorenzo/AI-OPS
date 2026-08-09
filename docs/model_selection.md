# Model Selection

AI-OPS lets you bring-your-own-LLM. Under the hood it uses [litellm](https://github.com/BerriAI/litellm/), so virtually any provider litellm supports can drive the agent, and any OpenAI-compatible endpoint works even when litellm doesn't know it by name.

You point AI-OPS at a model with three levers.

## The three levers

| Lever | API (env var) | Programmatic (`ModelConfig`) | Required |
|---|---|---|---|
| Fully-qualified model id | `AI_OPS_MODEL` | `model` | Yes |
| Provider API base URL | `LLM_API_BASE` | `api_base` | No |
| Provider API key | `LLM_API_KEY` | `api_key` | No |

The **model id** is always `provider/model`, for example `openai/gpt-4o` or `anthropic/claude-sonnet-4`. Some providers use a third segment, for example `huggingface/namespace/repo`.

The **API base** and **API key** are optional. Hosted providers usually infer the base from the provider prefix and only need a key; self-hosted or custom endpoints need an explicit base (see [OpenAI-compatible endpoints](#openai-compatible-endpoints) below).

Programmatic setup passes the same three values through `ModelConfig`:

```python
from ai_ops.core.llm import ModelConfig, build_inference_client

client = build_inference_client(ModelConfig(
    model="hosted_vllm/gemma-3-27b-it",
    api_base="https://your-llm-endpoint/v1/",  # optional
    api_key="your-provider-key",               # optional
))
```

## What the model must support

- **Tool use (required).** The agent does everything through tool calls, a model that can't call tools can't operate. Nothing enforces this at startup, so choosing a tool-capable model is on you. After startup you can confirm what AI-OPS detected with `GET /model` (the `tool_use` field).
- **Consecutive user messages in the chat template.** AI-OPS appends an ephemeral index to the last user message and its context management can drop intermediate assistant turns, so the conversation can contain two user messages in a row. Hosted providers handle this transparently; a self-hosted model whose chat template rejects consecutive user messages will error. If you control the template, make sure it tolerates them.
- **A large enough context window.** If the window can't be detected automatically (common with self-hosted endpoints), set it yourself with `LLM_MAX_CONTEXT_LENGTH`. This value also feeds the [layered context view](reference/context-management.md) and the token accounting behind `GET /conversation/{short_id}/usage`.

## Providers litellm supports

For any provider litellm knows, set the model id (and usually a key). The base is implied by the provider prefix. A few examples:

```bash
# OpenAI
AI_OPS_MODEL=openai/gpt-4o
LLM_API_KEY=sk-...

# Anthropic
AI_OPS_MODEL=anthropic/claude-sonnet-4
LLM_API_KEY=sk-ant-...
```

litellm resolves the provider, applies rate-limit retries, and reports the model's capabilities. See the [litellm provider list](https://docs.litellm.ai/docs/providers) for the exact prefixes and per-provider notes.

## OpenAI-compatible endpoints

Plenty of endpoints speak the OpenAI API without being an explicitly supported litellm provider: a local vLLM server, an inference gateway, a niche host. For these, use the **`hosted_vllm/` prefix** and set the API base:

```bash
# self-hosted vLLM (or any OpenAI-compatible server)
AI_OPS_MODEL=hosted_vllm/gemma-3-27b-it
LLM_API_BASE=https://your-vllm-endpoint/v1/
LLM_API_KEY=whatever-the-endpoint-expects   # if it needs one
LLM_MAX_CONTEXT_LENGTH=32768                 # set the window explicitly
```

`hosted_vllm/` tells litellm to treat the endpoint as OpenAI-compatible and route to your `api_base` instead of a known provider.

## How capabilities are detected

When AI-OPS builds the client it fills in a `ModelMetadata` (`provider`, `model_id`, `max_context_length`, `tool_use`, `reasoning`, `response_format`, `structured_output`), surfaced at `GET /model`. Detection tries, in order:

1. `litellm.get_model_info` for the model id.
2. If litellm doesn't know it, a lookup by model id against the public OpenRouter model list.
3. `LLM_MAX_CONTEXT_LENGTH`, if set, always overrides the detected context window.

For endpoints none of the catalogs know (a custom vLLM model name, say), detection can come up empty and fields like `tool_use` will read `false` even though the model does support it. That report is advisory: it does not block the agent from running. Trust your own knowledge of the model, and set `LLM_MAX_CONTEXT_LENGTH` so the context window is correct.

## See also

- [Getting Started](getting-started.md) for where these variables go in a deployment.
- [Configuration](configuration.md) for every environment variable.
- [Context Management](reference/context-management.md) for how the context window is used.
