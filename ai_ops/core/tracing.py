import os
import uuid
import functools
import urllib3
from typing import Callable

from ai_ops.core.conversation import Conversation
from ai_ops.core.utils import get_logger


_BACKEND_ENV = "AI_OPS_OBSERVABILITY_BACKEND"
_TRACKING_URI_ENV = "MLFLOW_TRACKING_URI"
# _USERNAME_ENV = "MLFLOW_TRACKING_USERNAME"
# _PASSWORD_ENV = "MLFLOW_TRACKING_PASSWORD"
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

    conversation: Conversation | None = kwargs.get("conversation")
    if conversation is None:
        conversation_arg_idx = next(
            (
                idx
                for idx, arg in enumerate(args)
                if isinstance(arg, Conversation)
            ),
            None
        )
        if conversation_arg_idx is None:
            session_id = f"unknown_{str(uuid.uuid4())}"
        else:
            session_id = args[conversation_arg_idx].id
    else:
        session_id = conversation.id

    with mlflow.start_span(name="orchestrator", span_type=SpanType.AGENT) as span:
        mlflow.update_current_trace(metadata={"mlflow.trace.session": session_id})
        yield from fn(*args, **kwargs)


def agent_trace(fn: Callable) -> Callable:

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        if _mlflow_ready:
            yield from _mlflow_trace(fn, *args, **kwargs)
        else:
            yield from fn(*args, **kwargs)

    return wrapper

configure()
