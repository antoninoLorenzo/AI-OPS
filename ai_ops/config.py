import os
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

# --- Environment Variables

API_BASE_ENV_NAME = "LLM_API_BASE"
API_KEY_ENV_NAME = "LLM_API_KEY"
API_MODEL_MAX_CONTEXT_LENGTH = "LLM_MAX_CONTEXT_LENGTH"

SKILL_VERIFY_INSTALLED_ENV = "SKILL_VERIFY_INSTALLED"
"""Whether to ensure binaries declared in skill requirements are available. If True, the agent 
won't start. Defaults to False."""
DEFAULT_SKILL_VERIFY_INSTALLED = False

TEMPERATURE_ENV = "AI_OPS_AGENT_TEMPERATURE"
DEFAULT_TEMPERATURE = 0.0
DEFAULT_MAX_CONTEXT_LENGTH = "32768"

CONFIRMATION_TIMEOUT_S = 300.0
"""
Default time to wait for a user confirmation before a blocked call is treated
as denied (not executed). Overridable per runner via `AgentConfig`.
"""

LOG_FILE_ENV = "AI_OPS_LOG_FILE"
"""The log file will be created at `AI_OPS_BASE_DIR/LOG_FILE_ENV`, needs to be a filename."""
LOG_LEVEL_ENV = "AI_OPS_LOG_LEVEL"
"""Lowercase."""
LOG_STDOUT_ENV = "AI_OPS_LOG_STDOUT"
"""Can be \"true\" or \"false\"."""

BASE_AGENT_ID = "react"

def build_environment() -> Path:
    # AI-OPS stuff goes into a single directory (for simplicity), this stuff currently includes 
    # logs, agent artifacts (workspace), persisted conversations and user-provided skills.
    # ```
    # ai_ops/
    #   user_skills/
    #   workspace/
    #   sessions/
    #   ai_ops.log
    # ```
    # For the choice of the base path I went for XDG_DATA_HOME because other options require 
    # root privileges (ex. /var/lib/ai_ops/) and even if we'll be in a container it's desirable 
    # executing as non-root user.
    # https://www.pathname.com/fhs/pub/fhs-2.3.html
    base = Path("~/.local/share/ai_ops").expanduser()
    if not base.exists():
        base.mkdir(exist_ok=True, parents=True)
    
    (base / "user_skills").mkdir(exist_ok=True)
    (base / "workspace").mkdir(exist_ok=True)
    (base / "sessions").mkdir(exist_ok=True)

    return base

T = TypeVar("T")

def env_or_default(env_name: str, default_value: T, cast_type: Callable[[str], T]) -> T: # noqa: UP047
    v = os.environ.get(env_name, str(default_value))

    if cast_type is bool:
        return v.lower() == "true"

    return cast_type(v)

AI_OPS_BASE_DIR = build_environment()
    
