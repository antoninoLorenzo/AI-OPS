import functools
import os
import uuid
from typing import Callable, Dict

import urllib3

from ai_ops.config import OBSERVABILITY_BACKEND_ENV
from ai_ops.core._mlflow import mlflow_ready, mlflow_trace, setup_mlflow
from ai_ops.core.log import get_logger, log_event, logging

_configured = False
_logger = get_logger(__name__)


def configure():
    # TODO: should probably move from there, all it's doing is call setup_mlflow,
    # that's startup setup stuff.
    global _configured
    if _configured:
        return
    
    backend = os.environ.get(OBSERVABILITY_BACKEND_ENV, "").lower()
    if backend == "mlflow":
        log_event(
            _logger, logging.INFO, 
            f"Identified Observability Backend: {OBSERVABILITY_BACKEND_ENV}=mlflow"
        )
        log_event(
            _logger, logging.DEBUG, "", 
            requests_ca_bundle_env=os.environ.get('REQUESTS_CA_BUNDLE')
        )
        setup_mlflow()

    _configured = True


# decorator for the agent orchestrator, switches between tracing backends based
# on which is enabled, defaults to no tracing.
def agent_trace(fn: Callable) -> Callable:

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        if mlflow_ready():
            yield from mlflow_trace(fn, *args, **kwargs)
        else:
            yield from fn(*args, **kwargs)

    return wrapper

configure()
