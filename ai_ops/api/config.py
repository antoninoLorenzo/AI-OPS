import os
import sys
from typing import Literal, List
from functools import lru_cache

from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict, JsonConfigSettingsSource

from ai_ops.config import (
    AI_OPS_BASE_DIR,
    API_BASE_ENV_NAME, 
    API_KEY_ENV_NAME, 
    API_MODEL_MAX_CONTEXT_LENGTH,
    TEMPERATURE_ENV,
    DEFAULT_TEMPERATURE,
    CONFIRMATION_TIMEOUT_S
)
from ai_ops.core.runner import AgentConfig
from ai_ops.core.conversation import StorageStrategy
from ai_ops.core.tools import DEFAULT_TOOLS
from ai_ops.core.context_management import CONTEXT_VIEW_REGISTRY
from ai_ops.core.tools import ToolMap
from ai_ops.core.tools.terminal.policy import COMMAND_POLICY_REGISTRY


class APISettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="AI_OPS_", extra="ignore")

    host: str = Field(default="127.0.0.1")
    auth_token: SecretStr | None = Field(default=None)
    storage_strategy: StorageStrategy | None = Field(default=StorageStrategy.JSONL)

    # note: the original ai_ops.config was implemented around core, so there's some duplication 
    # on how configuration should be managed overall (both ModelConfig and AgentConfig).
    model: str = Field(description="Fully Qualified Model ID.")
    llm_provider_base: str | None = Field(validation_alias=API_BASE_ENV_NAME)
    llm_provider_key: SecretStr | None = Field(validation_alias=API_KEY_ENV_NAME)
    

@lru_cache
def get_settings() -> APISettings:
    return APISettings()


class ContextViewSpec(BaseModel):
    kind: Literal["raw", "layered"] = "layered"
    params: dict = Field(default_factory=lambda: {"max_window_tokens": int(os.environ.get(API_MODEL_MAX_CONTEXT_LENGTH, "8192"))})


class CommandPolicySpec(BaseModel):
    kind: str
    params: dict = {}


class AgentConfigSpec(BaseSettings):
    model_config = SettingsConfigDict(json_file=AI_OPS_BASE_DIR / "agent_config.json")

    tools: List[str] = Field(default=[tool_cls.name for tool_cls in DEFAULT_TOOLS])
    context_view: ContextViewSpec = ContextViewSpec()
    command_policies: List[CommandPolicySpec] = []
    # in core.agent there's an `_AGENT_TEMPERATURE` taken from environmnet variables, 
    # we give precedence to the json config so it's either `DEFAULT_TEMPERATURE` or 
    # the one set in agent_config.json
    temperature: float = Field(default=DEFAULT_TEMPERATURE) 
    prompt_extension: str | None = Field(default=None)
    confirmation_timeout_s: float = CONFIRMATION_TIMEOUT_S

    @classmethod
    def settings_customise_sources(
        cls, 
        settings_cls, 
        init_settings, 
        env_settings, 
        dotenv_settings, 
        file_secret_settings
    ):
        return (init_settings, JsonConfigSettingsSource(settings_cls))



def build_agent_config() -> AgentConfig:
    spec = AgentConfigSpec()

    tools = []
    for tool_name in spec.tools:
        tool_cls = ToolMap.get(tool_name)
        if tool_cls is None:
            print(f"Invalid tool \"{tool_name}\"")
            sys.exit(1)
        tools.append(tool_cls)

    if spec.context_view.kind not in CONTEXT_VIEW_REGISTRY:
        print(f"Invalid context_view \"{spec.context_view.kind}\"")
        sys.exit(1)
    
    for policy in spec.command_policies:
        if policy.kind not in COMMAND_POLICY_REGISTRY:
            print(f"Invalid policy \"{policy.kind}\"")
            sys.exit(1)

    return AgentConfig(
        tools=tools,
        context_fn=CONTEXT_VIEW_REGISTRY[spec.context_view.kind](**spec.context_view.params),
        command_policies=tuple(
            COMMAND_POLICY_REGISTRY[policy.kind](**policy.params) for policy in spec.command_policies
        ),
        temperature=spec.temperature,
        prompt_extension=spec.prompt_extension,
        confirmation_timeout_s=spec.confirmation_timeout_s
    )