import os
from pathlib import Path

# --- Environment Variables

API_BASE_ENV_NAME = "LLM_API_BASE"
API_KEY_ENV_NAME = "LLM_API_KEY"
API_MODEL_MAX_CONTEXT_LENGTH = "LLM_MAX_CONTEXT_LENGTH"

SKILL_VERIFY_INSTALLED_ENV = "SKILL_VERIFY_INSTALLED"
"""Whether to ensure binaries declared in skill requirements are available. If True, the agent 
won't start. Defaults to False."""
DEFAULT_SKILL_VERIFY_INSTALLED = False

TEMPERATURE_ENV = "AI_OPS_AGENT_TEMPERATURE"
DEFAULT_TEMPERATURE = 0.4

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

OBSERVABILITY_BACKEND_ENV = "AI_OPS_OBSERVABILITY_BACKEND"
"""Only `mlflow` is supported."""

# Note: also requires MLFLOW_TRACKING_USERNAME and MLFLOW_TRACKING_PASSWORD but those are not 
# explicitly set by _mlflow.py.
# Optional: MLFLOW_TRACKING_INSECURE_TLS=true (not recommended ofc)
MLFLOW_TRACKING_URI_ENV = "MLFLOW_TRACKING_URI"
MLFLOW_EXPERIMENT_ENV = "MLFLOW_EXPERIMENT_NAME"


def build_environment() -> Path:
    # AI-OPS stuff goes into a single directory (for simplicity), this stuff currently includes 
    # logs, agent artifacts (workspace), persisted conversations and user-provided skills.
    # ```
    # ai_ops/
    #   user_skills/
    #   workspace/
    #   conversations/
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
    (base / "conversations").mkdir(exist_ok=True)

    return base

AI_OPS_BASE_DIR = build_environment()
    