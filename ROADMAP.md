# Roadmap

> Last updated: 09-08-2026 | current version 0.2.0

## Help Wanted

- [ ] Fix `extract_executables` handling of `sudo` ([`ai_ops.core.tools.terminal.utils`](ai_ops/core/tools/terminal/utils.py))
- [ ] More `CommandAdmissionPolicy` ([`ai_ops.core.tools.terminal.policy`](ai_ops/core/tools/terminal/policy.py))
- [ ] Nest autologged LLM spans under the async agent span in `amlflow_trace` ([`ai_ops.core._mlflow`](ai_ops/core/_mlflow.py)). The manual AGENT/TOOL spans nest correctly, but `litellm.acompletion` dispatches its mlflow success callback to litellm's `GLOBAL_LOGGING_WORKER` (a detached background task), so the LLM span is created after the agent span has ended and with no active span in context, mlflow then records it as a separate trace. mlflow's litellm autolog fix (mlflow#16982) only patches the *sync* thread pool, not this async worker. Tracked upstream: [mlflow#16697](https://github.com/mlflow/mlflow/issues/16697). Blocks the `parent_id`/`len(llm_spans) == 1` assertions in `test_async_llm_call_tracing` (currently `xfail`).
