import os
import logging
import litellm

LOG_FORMAT = "%(asctime)s - %(levelname)s - %(module)s - %(funcName)s:%(lineno)d - %(message)s"

# LiteLLM suppression
litellm.set_verbose = False
litellm.suppress_debug_info = True

# Do this once, at startup, not inside get_logger()
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)

# Quiet LiteLLM only
for name in (
    "litellm",
    "litellm_logging",
    "LiteLLM",
    "LiteLLM Router",
    "router",
    "utils",
    "token_counter",
):
    logger = logging.getLogger(name)
    logger.setLevel(logging.WARNING)
    logger.propagate = False
    logger.handlers.clear()  # removes any handler LiteLLM attached
    logger.addHandler(logging.NullHandler())


def get_logger(name: str) -> logging.Logger:
    log_level = os.environ.get("AI_OPS_LOG_LEVEL", "debug").lower()

    match log_level:
        case "debug":
            level = logging.DEBUG
        case "info":
            level = logging.INFO
        case "warning":
            level = logging.WARNING
        case "error":
            level = logging.ERROR
        case _:
            level = logging.DEBUG

    logger = logging.getLogger(name)
    logger.setLevel(level)
    return logger
