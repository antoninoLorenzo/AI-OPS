import os
from pathlib import Path

API_BASE_ENV_NAME = "LLM_API_BASE"
API_KEY_ENV_NAME = "LLM_API_KEY"
API_MODEL_MAX_CONTEXT_LENGTH = "LLM_MAX_CONTEXT_LENGTH"


def build_environment() -> Path:
    # AI-OPS stuff goes into a single directory (for simplicity), this stuff currently includes 
    # logs, agent artifacts (workspace), persisted conversations and user-provided skills.
    # ```
    # ai_ops/
    #   user_skills/
    #   workspace/
    #   ai_ops.db
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

    return base

AI_OPS_BASE_DIR = build_environment()
    