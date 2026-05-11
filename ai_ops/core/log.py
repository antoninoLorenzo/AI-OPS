import os
import sys
import logging
from pathlib import Path

import litellm


_LOG_FILE_ENV = "AI_OPS_LOG_FILE"
_LOG_LEVEL_ENV = "AI_OPS_LOG_LEVEL"
_LOG_STDOUT_ENV = "AI_OPS_LOG_STDOUT"

_DEFAULT_BASE_PATH = Path().home() / ".ai_ops"
if not _DEFAULT_BASE_PATH.exists():
    _DEFAULT_BASE_PATH.mkdir(exist_ok=True)
LOG_PATH = os.environ.get(_LOG_FILE_ENV, _DEFAULT_BASE_PATH / "logs.log")

LOG_LEVEL = os.environ.get(_LOG_LEVEL_ENV, "info").lower()
match LOG_LEVEL:
    case "debug":
        LOG_LEVEL = logging.DEBUG
    case "info":
        LOG_LEVEL = logging.INFO
    case "warning":
        LOG_LEVEL = logging.WARNING
    case "error":
        LOG_LEVEL = logging.ERROR
    case _:
        LOG_LEVEL = logging.INFO

LOG_TO_STDOUT = os.environ.get(_LOG_STDOUT_ENV, "false").lower()
LOG_TO_STDOUT = True if LOG_TO_STDOUT == "true" else False

LOG_FORMAT = "%(asctime)s - %(levelname)s - %(name)s - %(funcName)s:%(lineno)d - %(message)s"

_root = logging.getLogger()
_root.setLevel(LOG_LEVEL)
_root.handlers.clear()
_file_handler = logging.FileHandler(str(LOG_PATH))
_file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
_root.addHandler(_file_handler)

if LOG_TO_STDOUT:
    _stdout_handler = logging.StreamHandler(sys.stdout)
    _stdout_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    _root.addHandler(_stdout_handler)

# Shut the fuck up stuff
litellm.set_verbose = False
litellm.suppress_debug_info = True
for name in (
    "LiteLLM",
    "LiteLLM Router",
    "openai",
    "paramiko",
    "git", # mlflow dependency
    "asyncio",
    "urllib3",
    "httpcore"
):
    logger = logging.getLogger(name)
    logger.setLevel(logging.WARNING)
    logger.propagate = False
    logger.handlers.clear() 
    logger.addHandler(logging.NullHandler())


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    return logger


def log_event(logger: logging.Logger, level: int, message: str, **fields) -> None:
    # make logs more standardized
    parts = [message]
    for key, value in fields.items():
        parts.append(f"{key}={value!s}")
    logger.log(level, " ".join(parts), stacklevel=2)

