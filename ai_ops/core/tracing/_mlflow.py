import os
import traceback
import uuid
from collections.abc import Callable

import httpx
import urllib3

from ai_ops.config import MLFLOW_EXPERIMENT_ENV, MLFLOW_TRACKING_URI_ENV
from ai_ops.core.llm import InferenceClient
from ai_ops.core.log import get_logger, log_event, logging
from ai_ops.core.schema import ToolCallEvent, ToolResultEvent

MLFLOW_DEFAULT_EXPERIMENT = "AI-OPS"
MLFLOW_AGENT_TRACE_NAME = "orchestrator"

_logger = get_logger(__name__)
_mlflow_ready = False


def mlflow_ready():
    return _mlflow_ready


def mlflow_connect(tracking_uri: str, experiment_name: str):
    global _mlflow_ready
    import mlflow

    # If mlflow is unreachable disable it, check it before `set_experiment` since the call 
    # is blocking and either has no timeout or it's really high.
    try:
        insecure = os.environ.get("MLFLOW_TRACKING_INSECURE_TLS", "false").lower() == "true"
        httpx.get(tracking_uri, timeout=5.0, verify=(not insecure))
    except (httpx.ConnectError, httpx.ConnectTimeout) as err:
        log_event(
            _logger, logging.ERROR, "MLFlow: connection failed", 
            mlflow_tracking_uri=tracking_uri, mlflow_experiment=experiment_name, error=err
        )
        _mlflow_ready = False
        return

    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(experiment_name=experiment_name)
    log_event(
        _logger, logging.INFO, "MLFLow: established connection.",
        mlflow_tracking_uri=tracking_uri, mlflow_experiment=experiment_name
    )


def setup_mlflow():
    global _mlflow_ready
    import mlflow

    tracking_uri = os.environ.get(MLFLOW_TRACKING_URI_ENV)
    experiment = os.environ.get(MLFLOW_EXPERIMENT_ENV, MLFLOW_DEFAULT_EXPERIMENT)

    if tracking_uri:
        log_event(
            _logger, logging.INFO, "Setting up MLFlow",
            tracking_uri=tracking_uri, experiment_name=experiment
        )
        
        mlflow_connect(tracking_uri=tracking_uri, experiment_name=experiment)
        mlflow.litellm.autolog()
        _mlflow_ready = True

        if os.environ.get("MLFLOW_TRACKING_INSECURE_TLS", "false").lower() == "true":
            _logger.warning(f"Disabled SSL Verification for {tracking_uri}.")
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        log_event(
            _logger, logging.INFO, "MLFlow setup complete", 
            mlflow_tracking_uri=tracking_uri, mlflow_experiment=experiment
        )
    else:
        log_event(
            _logger, logging.WARNING, 
            f"Environment variable {MLFLOW_TRACKING_URI_ENV} not set: skipping MLFlow setup."
        )


def _resolve_trace_ids(args, kwargs) -> tuple[str, str]:
    """Resolve `(session_id, model_id)` from the orchestrator's call arguments.

    Both `orchestrator` and `aorchestrator` receive the `session` and
    `client` either as keyword or positional arguments, so we look in both.
    """
    # imported lazily: `storage` imports `ai_ops.core.tools`, and this module is
    # itself imported during `tools` initialization (via the prompt registry), so
    # a top-level import would create a circular import.
    from ai_ops.core.storage import Session

    # get session id from fn (orchestrator)
    session: Session | None = kwargs.get("session")
    if session is None:
        session_arg_idx = next(
            (
                idx for idx, arg in enumerate(args)
                if isinstance(arg, Session)
            ), None
        )
        session_id = args[session_arg_idx].uuid if session_arg_idx is not None \
            else f"unknown_{uuid.uuid4()!s}"
    else:
        session_id = session.uuid

    # get model being used
    model_client: InferenceClient | None = kwargs.get("client")
    if model_client is None:
        model_client_arg_idx = next(
            (
                idx for idx, arg in enumerate(args)
                if isinstance(arg, InferenceClient)
            ), None
        )
        model_id = args[model_client_arg_idx].model if model_client_arg_idx is not None \
            else "unknown"
    else:
        model_id = model_client.model

    return session_id, model_id


def mlflow_trace(fn: Callable, *args, **kwargs):
    import mlflow
    from mlflow.entities import SpanEvent, SpanStatus, SpanStatusCode, SpanType

    session_id, model_id = _resolve_trace_ids(args, kwargs)

    tool_call_spans: dict[str, tuple] = {} # tool_call_id -> (ctx, span)
    with mlflow.start_span(
        name=MLFLOW_AGENT_TRACE_NAME, 
        span_type=SpanType.AGENT,
        attributes={"ai.model.name": model_id}
    ) as agent_span:
        mlflow.update_current_trace(
            tags={"model": model_id},
            metadata={"mlflow.trace.session": session_id}
        )

        try:
            for event in fn(*args, **kwargs):
                # to trace tool calls here we have to use context manager manually
                if isinstance(event, ToolCallEvent):
                    ctx = mlflow.start_span(name=event.name, span_type=SpanType.TOOL)
                    span = ctx.__enter__()
                    span.set_inputs(event.args)
                    tool_call_spans[event.call_id] = (ctx, span)
                elif isinstance(event, ToolResultEvent):
                    ctx, span = tool_call_spans.pop(event.call_id, (None, None))
                    if span is not None:
                        span.set_outputs({"result": event.result.model_dump()})
                        ctx.__exit__(None, None, None)

                yield event
        except Exception as exc:
            agent_span.set_status(SpanStatus(SpanStatusCode.ERROR, str(exc)))
            agent_span.add_event(SpanEvent(
                name="Exception",
                attributes={
                    "exception.message": str(exc),
                    "exception.type": type(exc).__name__,
                    "exception.stacktrace": "".join(traceback.format_tb(exc.__traceback__))
                }
            ))
            raise
        finally:
            for ctx, span in tool_call_spans.values():
                ctx.__exit__(None, None, None)
            agent_span.end()


async def amlflow_trace(fn: Callable, *args, **kwargs):
    """Async-generator twin of `mlflow_trace`.

    Mirrors the synchronous tracer one-to-one; the only difference is that the
    wrapped orchestrator is driven with `async for`. `mlflow.start_span` returns
    a plain (sync) context manager, so it's still used with `with` here, and the
    manual tool-span lifecycle is identical.

    Caveat: unlike the sync path, autologged LLM spans from `litellm.acompletion`
    do NOT nest under the AGENT span. litellm dispatches the mlflow success
    callback to its `GLOBAL_LOGGING_WORKER` (a detached background task) which
    runs after this span has ended and with no active span in context, so mlflow
    records the LLM call as a separate trace. See ROADMAP.md / mlflow#16697.
    """
    import mlflow
    from mlflow.entities import SpanEvent, SpanStatus, SpanStatusCode, SpanType

    session_id, model_id = _resolve_trace_ids(args, kwargs)

    tool_call_spans: dict[str, tuple] = {} # tool_call_id -> (ctx, span)
    with mlflow.start_span(
        name=MLFLOW_AGENT_TRACE_NAME,
        span_type=SpanType.AGENT,
        attributes={"ai.model.name": model_id}
    ) as agent_span:
        mlflow.update_current_trace(
            tags={"model": model_id},
            metadata={"mlflow.trace.session": session_id}
        )

        try:
            async for event in fn(*args, **kwargs):
                # to trace tool calls here we have to use context manager manually
                if isinstance(event, ToolCallEvent):
                    ctx = mlflow.start_span(name=event.name, span_type=SpanType.TOOL)
                    span = ctx.__enter__()
                    span.set_inputs(event.args)
                    tool_call_spans[event.call_id] = (ctx, span)
                elif isinstance(event, ToolResultEvent):
                    ctx, span = tool_call_spans.pop(event.call_id, (None, None))
                    if span is not None:
                        span.set_outputs({"result": event.result.model_dump()})
                        ctx.__exit__(None, None, None)

                yield event
        except Exception as exc:
            agent_span.set_status(SpanStatus(SpanStatusCode.ERROR, str(exc)))
            agent_span.add_event(SpanEvent(
                name="Exception",
                attributes={
                    "exception.message": str(exc),
                    "exception.type": type(exc).__name__,
                    "exception.stacktrace": "".join(traceback.format_tb(exc.__traceback__))
                }
            ))
            raise
        finally:
            for ctx, span in tool_call_spans.values():
                ctx.__exit__(None, None, None)
            agent_span.end()
