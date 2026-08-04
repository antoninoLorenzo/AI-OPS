# Developer Notes

> The project is still an heavy wip, so this is just a snapshot of how things work today.

## Tools (`ai_ops.core.tools`)

### Builtin Tools 

| Tool | Description | 
| ---- | ----------- | 
| `ThinkTool` | Lets non-reasoning LLMs generate thoughts. |
| `WhiteboardWrite` | Write tuples (`name`, `description`, `content`) when a new finding (ex. found host running web server) or when it tried something but failed (ex. SQLi attempt failed) | .
| `WhiteboardRead` | Currently the index (that gets injected) is added to the last user message so it's technically useless. |
| `LoadSkill` | Lets the agent load Agent Skills | 
| `WriteFile` | Lets the agent write files (ex. exploit scripts). | 
| `Terminal` | Interface for a shell implementation, currently only `BashShell` (technically it's `/bin/sh` lol). | 


## Context Management (`ai_ops.core.context_management`)

Yeah modern LLMs have really long context windows, however there are two good reasons two employ context compaction (reducing the amount of text given to an LLM):
1. LLMs ain't cheap, whether you're paying for token consumption (-> want to reduce the amount of tokens being used), or deploying your own (-> have to reduce the maximum allowed context to reduce KV size).
2. LLMs struggle when there's too much going on in the given context.

For this reason the AI-OPS agent can be given a `ContextView` that takes in input a message list (the conversation) and returns a filtered copy:
```python
class ContextView(Protocol):
    def __call__(self, messages: List[Message]) -> List[Message]: ...
```
> Implementations return a deep-copied message list because we don't want to modify the original list. Deep copying is acceptable because messages are text-only; it would need revisiting if binary blobs (base64 images etc.) were introduced.

Currently there are two implementations: `RawContextView` (default) just wastes memory by returning a deep copy (lol), `LayeredContextView` described below.

### LayeredContextView

Context compaction is usually done through LLM-summarization, though we have the `WhiteboardWrite` tool that act as an in-loop summarization primitive so I'm giving a try at heuristic-driven compaction (we'll see if it pays off with benchmarks).

The strategy is "layered" because it operates at two levels of depth within the message list (ah, naming): the last whiteboard write is treated as a checkpoint, so the **pre-checkpoint** layer is just dropping everything before, **active-window** treats what comes after.
> System and user messages are never touched of course.

The active window strategy drops `Think` and `WriteFile` tool calls older than `max_file_write` and `max_think`, plus it truncates the output of `Terminal` (or `terminal_alias` if there's a different implementation fucking benchmarks) if it exceeds `truncation_threshold * max_window_tokens`. 

> There's an interesting project out there that could be the backbone for another `ContextView` implementation or replace/be called withing active-window: https://github.com/chopratejas/headroom.

