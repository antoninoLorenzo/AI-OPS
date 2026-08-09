# Built-in Tools

Tools are how the agent acts. On every step the model may call one or more of the tools it was given; AI-OPS validates the call against the tool's schema, runs it, and feeds the result back into the conversation.

Which tools an agent has is chosen per deployment: by name in [`agent_config.json`](../configuration.md#agent)'s `tools`, or programmatically
through `AgentConfig(tools=[...])`. The default set (`DEFAULT_TOOLS`) is `load_skill`, `think`, `write_whiteboard`, `write_file`, and `terminal`.

| Tool | In default set | Purpose |
|---|---|---|
| `load_skill` | Yes | Load an [Agent Skill](skills.md) on demand, pulling task-specific instructions into context only when the agent decides it needs them. |
| `think` | Yes | A reasoning scratchpad. Lets non-reasoning models plan a step and record intent before acting. Input: a single `thought` string. |
| `write_whiteboard` | Yes | Record a finding or a failed attempt as `(name, description, content)`. The `description` feeds an always-in-context index; the full `content` is stored out of the way. Also acts as the checkpoint signal for the [layered context view](context-management.md). |
| `read_whiteboard` | No | Read a stored whiteboard entry back by `name`. Rarely needed, since the whiteboard index is already injected into context each turn. |
| `write_file` | Yes | Write a file (for example an exploit script) into the session workspace. Paths are confined to that workspace. |
| `terminal` | Yes | Execute a shell command in the session workspace. Input: a `command` string (plus optional session, interactive, and timeout fields). Subject to [command policies](../command-policy.md) and, in supervised mode, to confirmation. |
| `stop` | Always injected | Orchestration primitive the agent calls to signal the objective is reached; it produces the terminal `stop` event. Always available and cannot be set through `tools`. |

## Enabling tools

For the API, list the tool names in `agent_config.json`:

```json
{ "tools": ["load_skill", "think", "write_whiteboard", "write_file", "terminal"] }
```

An unknown tool name aborts startup. Programmatically, pass the tool classes:

```python
from ai_ops.core.tools import DEFAULT_TOOLS
AgentConfig(tools=DEFAULT_TOOLS)
```

## Confirmation and safety

Tools that perform sensitive operations are gated in supervised mode: before the call runs, the user is asked to approve it. Today the `terminal` tool is the one that goes through this path. In unsupervised mode a gated call is skipped without asking. Independently of the mode, [command policies](../command-policy.md) restrict which executables the terminal tool may run.

See [Add a Tool](../how-to/add-a-tool.md) to write and register your own, and [Context Management](context-management.md) for how tool output is kept within the model's context window.
