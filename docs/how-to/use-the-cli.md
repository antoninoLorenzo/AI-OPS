# Use the CLI

The AI-OPS CLI is a small terminal client for the API. It is a minimal prototype: it opens a conversation, sends your messages, and renders the agent's
event stream (reasoning, tool calls, results) as it arrives. It holds no agent state of its own, so it works against any reachable API.

This guide assumes the API is already running. If it isn't, start there: [Getting Started](../getting-started.md) or [Run the API Server](run-the-api-server.md).

## Install and launch

The CLI is run from source, from the repository's `cli/` directory:

```bash
cd cli
npm install
npm start -- --base-url http://127.0.0.1:8000
```

Everything after `--` is passed to the client. If the API requires a token, add `--api-key`:

```bash
npm start -- --base-url http://127.0.0.1:8000 --api-key "$AI_OPS_AUTH_TOKEN"
```

On startup the client checks the API is reachable (`GET /health`), opens a conversation (or resumes one), and fetches model metadata for the status bar. Any startup-fatal problem (unreachable API, malformed config, a missing resumed conversation) prints a message and exits with status `1`.

## Configuration

Configuration comes from command-line flags and an optional JSON file. Flags take precedence over the file.

### Flags

| Flag | Description |
|---|---|
| `--base-url <url>` | API base URL. Required (must be a valid URL) unless set in the config file. |
| `--api-key <key>` | API key, sent as `X-AI-OPS-ApiKey` on every request. |
| `--mode <supervised\|unsupervised>` | Agent mode, set at startup only. See [Modes](#modes). |
| `--resume <short_id>` | Resume an existing conversation instead of creating one. See [Resume a conversation](#resume-a-conversation). |

### Config file

If `~/.config/ai_ops/cli.json` exists it is loaded and merged under the flags. A missing file is not an error; a present but malformed file (invalid JSON, or a value that fails validation) is fatal at startup.

```json
{
  "base_url": "http://127.0.0.1:8000",
  "api_key": "<api_key>",
  "mode": "supervised",
  "resume": 1
}
```

With a config file in place you can launch with no flags, and override any single value when you need to:

```bash
npm start                              # uses cli.json
npm start -- --mode unsupervised       # cli.json, but override the mode
```

See [Configuration](../configuration.md#cli) for the full reference.

## The screen

The screen is laid out top to bottom: the transcript, the input line, then the status bar.

The transcript renders the agent's work as typed blocks: reasoning, assistant text, and one block per tool (terminal commands, loaded skills,
whiteboard notes, written files). Reasoning is hidden by default; press **Ctrl+R** to toggle it.

The status bar sits at the bottom and summarizes the session:

```
<model-id> (<provider>) · <MODE> · #<short_id> · <used>/<max>   ctrl+r reasoning
```

That is the active model and provider, the run mode, the conversation's `short_id`, and token usage against the model's context window (`<used>/?` when
the window is unknown, see [Model Selection](../model_selection.md)), followed by the global key hints.

It is drawn last on every frame, so it stays in view at the bottom of the terminal as the transcript grows past the window and scrolls up behind it.

## Sending messages and controls

Type a request and press **Enter** to send it. The client streams the agent's response into the transcript.

| Key | Action |
|---|---|
| `Enter` | Submit the current line. |
| `Shift+Enter` | Insert a newline (multi-line input). |
| `Tab` | Complete a slash command from the suggestion list. |
| `↑` / `↓` | Move through the slash-command suggestions. |
| `←` / `→`, `Backspace` | Edit the current line. |
| `Ctrl+R` | Toggle reasoning visibility. |

### Slash commands

Type `/` to see the available commands (they complete with `Tab`):

| Command | Action |
|---|---|
| `/stop` | Ask the agent to stop. The stop is non-preemptive: it halts after the current event finishes. |
| `/exit` | Close the conversation on the server and quit the CLI. |

## Modes

The mode is chosen at startup (`--mode`, default `supervised`) and cannot be
toggled at runtime.

- **`supervised`** (default): before a sensitive tool call runs, the agent pauses and the input is replaced by a confirmation prompt. Press **`y`** to approve or **`n`** to reject; if several calls are queued, the prompt shows how many more are waiting. A rejection (or a confirmation timeout on the server) is reported back to the agent as a normal tool result, and it continues from there.
- **`unsupervised`**: sensitive calls are skipped without asking (never executed), and the iteration cap is raised so the agent can run longer unattended.

To constrain what the terminal tool may execute in either mode, use [Command Policies](../command-policy.md).

## Follow-ups while the agent runs

You don't have to wait for the agent to finish. While a run is in progress you can:

- **Enqueue one follow-up message** by typing it and pressing `Enter`. It is spliced into the conversation as soon as the agent has no pending tool calls. Only one message can be queued at a time; until it's consumed, new prompts are blocked (slash commands still work).
- **Stop the agent** with `/stop`.

## Resume a conversation

Conversations persist on the server (with the default JSONL storage), so you can reconnect to one by its `short_id`:

```bash
npm start -- --base-url http://127.0.0.1:8000 --resume 1
```

The client loads the stored event stream into the transcript and restores prior token usage before handing control back to you. Resuming a `short_id` that doesn't exist is a startup-fatal error.

## Troubleshooting

**`No conversation with short_id=<n>`**

The `--resume` flag points to a conversation the server doesn't have. You can inspect the `index.json` file (`short_id` -> `conversation_id`) as follows:
```bash
docker exec -it CONTAINER_ID cat `/home/aiops/.local/share/ai_ops/index.json`
```

