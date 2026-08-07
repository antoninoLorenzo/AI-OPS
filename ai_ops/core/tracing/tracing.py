import functools
import inspect
import os
from collections.abc import Callable

from ai_ops.config import OBSERVABILITY_BACKEND_ENV
from ai_ops.core.log import get_logger, log_event, logging
from ai_ops.core.tracing._mlflow import (
    amlflow_trace,
    mlflow_ready,
    mlflow_trace,
    setup_mlflow,
)

_configured = False
_logger = get_logger(__name__)


def configure_tracing():
    """Configure the observability backend (currently only mlflow).

    This is startup setup and must be called explicitly by the entrypoint: the
    API does it in its lifespan; programmatic core users have to call it
    themselves (before running an agent) for tracing to be active. It is not run
    at import time so importing `ai_ops.core` has no observability side effects.
    Idempotent.
    """
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


def agent_trace(fn: Callable) -> Callable:
    """
    Decorator for the agent orchestrator, switches between tracing backends based
    on which is enabled, defaults to no tracing.
    """

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        if mlflow_ready():
            yield from mlflow_trace(fn, *args, **kwargs)
        else:
            yield from fn(*args, **kwargs)

    @functools.wraps(fn)
    async def a_wrapper(*args, **kwargs):
        if mlflow_ready():
            async for event in amlflow_trace(fn, *args, **kwargs):
                yield event
        else:
            async for event in fn(*args, **kwargs):
                yield event

    if inspect.isasyncgenfunction(fn):
        return a_wrapper
    else:
        return wrapper