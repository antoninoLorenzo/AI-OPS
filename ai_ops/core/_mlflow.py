import os
import urllib3
import traceback
from typing import Callable

from ai_ops.core.llm import InferenceClient, ModelMetadata
from ai_ops.core.conversation import Conversation
from ai_ops.core.schema import ToolCallEvent, ToolResultEvent
from ai_ops.core.log import get_logger, log_event, logging

TRACKING_URI_ENV = "MLFLOW_TRACKING_URI"
EXPERIMENT_ENV = "MLFLOW_EXPERIMENT_NAME"
DEFAULT_EXPERIMENT = "AI-OPS"
AGENT_TRACE_NAME = "orchestrator"

_logger = get_logger(__name__)
_mlflow_ready = False


def mlflow_ready():
    global _mlflow_ready
    return _mlflow_ready


def mlflow_connect(tracking_uri: str, experiment_name: str):
    global _mlflow_ready
    import mlflow

    mlflow.set_tracking_uri(tracking_uri)
    # it automatically creates the experiment with `experiment_name` if it doesn't exists
    mlflow.set_experiment(experiment_name=experiment_name)


def setup_mlflow():
    global _mlflow_ready
    import mlflow

    tracking_uri = os.environ.get(TRACKING_URI_ENV)
    experiment = os.environ.get(EXPERIMENT_ENV, DEFAULT_EXPERIMENT)

    if tracking_uri:
        log_event(
            _logger, logging.INFO, "Setting up MLFlow",
            tracking_uri=tracking_uri, experiment_name=experiment
        )
        
        mlflow_connect(tracking_uri=tracking_uri, experiment_name=experiment)
        mlflow.litellm.autolog()
        _mlflow_ready = True

        if os.environ.get("MLFLOW_TRACKING_INSECURE_TLS", False):
            _logger.warning(f"Disabled SSL Verification for {tracking_uri}.")
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        log_event(
            _logger, logging.INFO, "MLFlow setup complete", 
            mlflow_tracking_uri=tracking_uri, mlflow_experiment=experiment
        )
    else:
        log_event(
            _logger, logging.WARNING, 
            f"Environment variable {TRACKING_URI_ENV} not set: skipping MLFlow setup."
        )


def mlflow_trace(fn: Callable, *args, **kwargs):
    import mlflow
    from mlflow.entities import SpanType, SpanEvent, SpanStatus, SpanStatusCode

    # get conversation id from fn (orchestrator)
    conversation: Conversation | None = kwargs.get("conversation")
    if conversation is None:
        conversation_arg_idx = next(
            (
                idx for idx, arg in enumerate(args)
                if isinstance(arg, Conversation)
            ), None
        )
        session_id = args[conversation_arg_idx].id if conversation_arg_idx is not None \
            else f"unknown_{str(uuid.uuid4())}"
    else:
        session_id = conversation.id

    # get model being used 
    model_client: InferenceClient | None = kwargs.get("client")
    if model_client is None:
        model_client_arg_idx = next(
            (
                idx for idx, arg in enumerate(args)
                if isinstance(arg, InferenceClient)
            ), None
        )
        model_id = args[model_client_arg_idx].model if model_client_arg_idx \
            else "unknown"
    else:
        model_id = model_client.model

    tool_call_spans: Dict[str, tuple] = {} # tool_call_id -> (ctx, span)
    with mlflow.start_span(
        name=AGENT_TRACE_NAME, 
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
