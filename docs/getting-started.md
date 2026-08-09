# Getting Started

## Prerequisites

- **Docker**: the API runs in a container built from `kalilinux/kali-rolling` with the offensive tooling (nmap, seclists, ...) already installed.
- **Node.js** (for the CLI): the CLI is a small terminal client run from source. See [Use the CLI](how-to/use-the-cli.md).
- **An LLM you can reach**: a provider API key, or a self-hosted OpenAI-compatible endpoint (e.g. vLLM). The model must support tool use. The three things you always need are a **fully-qualified model id**, and optionally an **API base** and an **API key**. See [Model Selection](model_selection.md).

## Deploy the API

> A prebuilt image isn't published yet. When it is, a "Pull the image" section will go here, above the from-source path below.

### Build from source

Build the image by running the following from the repository root:

```bash
docker build -f docker/Dockerfile -t ai-ops:api-dev .
```

The container reads configuration from environment variables. Put them in a `.env` file (loaded automatically):

```bash
# .env
AI_OPS_MODEL=hosted_vllm/gemma-3-27b-it     # required
LLM_API_BASE=https://your-llm-endpoint/v1/  # your provider / vLLM base URL
LLM_API_KEY=your-provider-key               # your provider key
```

`AI_OPS_MODEL` is the only required variable. `LLM_API_BASE` and `LLM_API_KEY` depend on your provider. See [Model Selection](model_selection.md) and [Configuration](configuration.md) for more details.

> **Auth.** Bound to localhost, the API starts without an auth token (it logs a warning). The moment you expose it on any other host it **refuses to start without `AI_OPS_AUTH_TOKEN`**. See [Run the API Server](how-to/run-the-api-server.md#exposing-it-beyond-localhost).

Run the API:

```bash
docker run --rm -p 8000:8000 --env-file .env \
    --volume ai-ops-data:/home/aiops/.local/share/ai_ops \
    --cap-add=NET_RAW --cap-add=NET_ADMIN \
    --security-opt=no-new-privileges \
    ai-ops:api-dev
```

- `NET_RAW` and `NET_ADMIN` let tools like `nmap` send raw packets.
- The volume persists sessions, logs, the agent workspace, and user skills across restarts (see [Storage Layout](reference/storage.md)).
- To supply your own agent configuration or skills, bind-mount them into the container. See [Run the API Server](how-to/run-the-api-server.md#supplying-config-and-skills) and [Configuration](configuration.md#agent).

Check it's up:

```bash
curl http://127.0.0.1:8000/health
# {"status":"ok"}

curl http://127.0.0.1:8000/model
# {"provider":"...","model_id":"...","max_context_length":32768,"tool_use":true,...}
```

`/model` reports the capabilities AI-OPS detected for your model. Make sure `tool_use` is `true`: the agent drives everything through tool calls, so a model without tool use can't do useful work. Nothing enforces this at startup, so it's on you to pick a tool-capable model ([Model Selection](model_selection.md)).

## Connect the CLI

The CLI is a thin client. It works as long as it can reach the API. From the repository's `cli/` directory:

```bash
cd cli
npm install
npm start -- --base-url http://127.0.0.1:8000
```

If you set `AI_OPS_AUTH_TOKEN` on the server, pass it to the client too:

```bash
npm start -- --base-url http://127.0.0.1:8000 --api-key "$AI_OPS_AUTH_TOKEN"
```

On startup the CLI checks the API is reachable, opens a conversation, and shows the active model in its header. The full flag list, the optional config file, in-app keys, and slash commands are in [Use the CLI](how-to/use-the-cli.md).

## Run your first task

Type a request and press **Enter**:

```
find open services on 10.10.10.5 and identify what's running
```

The agent streams its work back into the transcript: its reasoning, the tools it calls (terminal commands, skills it loads, whiteboard notes), and their results.

By default the CLI runs in **supervised** mode: before a sensitive command runs, the agent pauses and asks you to approve it. Approve or deny at the prompt; a denial (or a timeout) is reported back to the agent, which adapts and continues. `unsupervised` mode skips those prompts and raises the iteration cap. See [Use the CLI](how-to/use-the-cli.md#modes) and [Command Policies](command-policy.md) for how to constrain what the agent may run.

When you're done, type `/exit` (or `/stop` to halt the agent mid-task without quitting).

## Where to go next

- **[Model Selection](model_selection.md)**: choose a model that works, including self-hosted and OpenAI-compatible endpoints.
- **[Use the CLI](how-to/use-the-cli.md)**: every flag, key, and command.
- **[Run the API Server](how-to/run-the-api-server.md)**: deployment details, exposing beyond localhost, driving the API without the CLI.
- **[Run the Agent Programmatically](how-to/run-the-agent-programmatically.md)**: use the `core` interface directly, without the API or CLI.
- **[Configuration](configuration.md)**: all API, CLI, and agent settings.
- **[Command Policies](command-policy.md)**: allow-list what the terminal tool may execute.
