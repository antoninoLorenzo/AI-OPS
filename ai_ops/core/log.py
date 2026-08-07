import logging
import os
import sys

import litellm

from ai_ops.config import AI_OPS_BASE_DIR, LOG_FILE_ENV, LOG_LEVEL_ENV, LOG_STDOUT_ENV


def suppress_logger(name: str):
    logger = logging.getLogger(name)
    logger.setLevel(logging.WARNING)
    logger.propagate = False
    logger.handlers.clear() 
    logger.addHandler(logging.NullHandler())


def setup_logging():
    log_path = AI_OPS_BASE_DIR / os.environ.get(LOG_FILE_ENV, "logs.log")
    log_level = os.environ.get(LOG_LEVEL_ENV, "info").lower()

    match log_level:
        case "debug":
            log_level = logging.DEBUG
        case "info":
            log_level = logging.INFO
        case "warning":
            log_level = logging.WARNING
        case "error":
            log_level = logging.ERROR
        case _:
            log_level = logging.INFO

    log_to_stdout = os.environ.get(LOG_STDOUT_ENV, "false").lower()
    log_to_stdout = log_to_stdout == "true"

    log_format = "%(asctime)s - %(levelname)s - %(name)s - %(funcName)s:%(lineno)d - %(message)s"

    _root = logging.getLogger()
    _root.setLevel(log_level)
    _root.handlers.clear()
    _file_handler = logging.FileHandler(str(log_path))
    _file_handler.setFormatter(logging.Formatter(log_format))
    _root.addHandler(_file_handler)

    if log_to_stdout:
        _stdout_handler = logging.StreamHandler(sys.stdout)
        _stdout_handler.setFormatter(logging.Formatter(log_format))
        _root.addHandler(_stdout_handler)

    # litellm edge-case
    litellm.set_verbose = False
    litellm.suppress_debug_info = True

    yappers = (
        "LiteLLM",
        "LiteLLM Router",
        "openai",
        "paramiko",
        "git", # mlflow dependency
        "asyncio",
        "urllib3",
        "httpcore",
        "mlflow.store.model_registry.abstract_store"
    )

    for name in yappers:
        suppress_logger(name)


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    return logger


def log_event(logger: logging.Logger, level: int, message: str, **fields) -> None:
    # make logs more standardized
    parts = [message]
    for key, value in fields.items():
        parts.append(f"{key}={value!s}")
    logger.log(level, " ".join(parts), stacklevel=2)


setup_logging()