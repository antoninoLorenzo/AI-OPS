import os
import uuid
import functools
import urllib3
from typing import Callable, Dict

from ai_ops.core.llm import InferenceClient, ModelMetadata
from ai_ops.core.conversation import Conversation
from ai_ops.core.utils import get_logger
from ai_ops.core.schema import ToolCallEvent, ToolResultEvent


AGENT_TRACE_NAME = "orchestrator"
_BACKEND_ENV = "AI_OPS_OBSERVABILITY_BACKEND"
_TRACKING_URI_ENV = "MLFLOW_TRACKING_URI"
_EXPERIMENT_ENV = "MLFLOW_EXPERIMENT_NAME"
_DEFAULT_EXPERIMENT = "AI-OPS"

_configured = False
_mlflow_ready = False

_logger = get_logger(__name__)


def configure():
    global _configured
    if _configured:
        return
    
    backend = os.environ.get(_BACKEND_ENV, "").lower()
    if backend == "mlflow":
        _logger.info("Setting up MLFlow")
        _logger.debug(f"REQUESTS_CA_BUNDLE={os.environ.get('REQUESTS_CA_BUNDLE')}")
        _setup_mlflow()

    _configured = True


def _setup_mlflow():
    global _mlflow_ready
    import mlflow

    tracking_uri = os.environ.get(_TRACKING_URI_ENV)
    experiment = os.environ.get(_EXPERIMENT_ENV, _DEFAULT_EXPERIMENT)

    if tracking_uri:
        _logger.info(f"MLFlow tracking_uri={tracking_uri} experiment_name={experiment}")
        mlflow.set_tracking_uri(tracking_uri)
        mlflow.set_experiment(experiment_name=experiment)
        mlflow.litellm.autolog()
        _mlflow_ready = True

        if os.environ.get("MLFLOW_TRACKING_INSECURE_TLS", False):
            _logger.warning(f"Disabled SSL Verification for {tracking_uri}.")
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    else:
        _logger.warning(f"Environment variable {_TRACKING_URI_ENV} not set: skipping MLFlow setup.")


def _mlflow_trace(fn: Callable, *args, **kwargs):
    import mlflow
    from mlflow.entities import SpanType

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


# decorator for the agent orchestrator, switches between tracing backends based
# on which is enabled, defaults to no tracing.
def agent_trace(fn: Callable) -> Callable:

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        if _mlflow_ready:
            yield from _mlflow_trace(fn, *args, **kwargs)
        else:
            yield from fn(*args, **kwargs)

    return wrapper

configure()
