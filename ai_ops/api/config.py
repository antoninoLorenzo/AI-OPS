import sys
from functools import lru_cache

from pydantic import BaseModel, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, JsonConfigSettingsSource, SettingsConfigDict

from ai_ops.config import (
    AI_OPS_BASE_DIR,
    API_BASE_ENV_NAME,
    API_KEY_ENV_NAME,
    CONFIRMATION_TIMEOUT_S,
    DEFAULT_TEMPERATURE,
)
from ai_ops.core.context_management import ContextTransformType
from ai_ops.core.log import get_logger, log_event, logging
from ai_ops.core.runner import AgentConfig
from ai_ops.core.storage import StorageStrategy
from ai_ops.core.tools import DEFAULT_TOOLS, ToolRegistry
from ai_ops.core.tools.terminal.policy import COMMAND_POLICY_REGISTRY

_logger = get_logger(__name__)


class APISettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="AI_OPS_", extra="ignore")

    host: str = Field(default="127.0.0.1")
    port: int = Field(default=8000)
    auth_token: SecretStr | None = Field(default=None)
    allowed_hosts: list[str] = Field(default_factory=lambda: ["127.0.0.1", "localhost"])
    storage_strategy: StorageStrategy | None = Field(default=StorageStrategy.JSONL)

    # note: the original ai_ops.config was implemented around core, so there's some duplication 
    # on how configuration should be managed overall (both ModelConfig and AgentConfig).
    model: str = Field(description="Fully Qualified Model ID.")
    llm_provider_base: str | None = Field(default=None, validation_alias=API_BASE_ENV_NAME)
    llm_provider_key: SecretStr | None = Field(default=None, validation_alias=API_KEY_ENV_NAME)

    # additional development flags
    debug: bool = Field(default=False)

    @field_validator("allowed_hosts", mode="before")
    @classmethod
    def split_comma_separated(cls, v: object) -> object:
        if isinstance(v, str):
            return [val.strip() for val in v.split(",")]
        return v
    

@lru_cache
def get_settings() -> APISettings:
    return APISettings()


class CommandPolicySpec(BaseModel):
    kind: str
    params: dict = {}


class AgentConfigSpec(BaseSettings):
    model_config = SettingsConfigDict(json_file=AI_OPS_BASE_DIR / "agent_config.json")

    tools: list[str] = Field(default=[tool_cls.name for tool_cls in DEFAULT_TOOLS])
    context_transforms: list[ContextTransformType] = Field(
        default_factory=lambda: [ContextTransformType.CHECKPOINT]
    )
    command_policies: list[CommandPolicySpec] = []
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
    agent_spec = AgentConfigSpec()
    log_event(_logger, logging.DEBUG, "Loaded AgentConfigSpec", agent_spec=agent_spec)

    tools = []
    for tool_name in agent_spec.tools:
        tool_spec = ToolRegistry.get(tool_name)
        if tool_spec is None:
            print(f"Invalid tool \"{tool_name}\"")
            sys.exit(1)
        tools.append(tool_spec.tool)

    for policy in agent_spec.command_policies:
        if policy.kind not in COMMAND_POLICY_REGISTRY:
            print(f"Invalid policy \"{policy.kind}\"")
            sys.exit(1)

    log_event(
        _logger, logging.INFO, "Agent Configuration Loaded",
        tools=", ".join([tool.name for tool in tools]),
        context_transforms=", ".join(agent_spec.context_transforms),
        command_policies=", ".join([policy.kind for policy in agent_spec.command_policies]),
        temperature=agent_spec.temperature,
        confirmation_timeout_s=agent_spec.confirmation_timeout_s
    )

    return AgentConfig(
        tools=tools,
        context_transforms=tuple(agent_spec.context_transforms),
        command_policies=tuple(
            COMMAND_POLICY_REGISTRY[policy.kind](**policy.params) for policy in agent_spec.command_policies
        ),
        temperature=agent_spec.temperature,
        prompt_extension=agent_spec.prompt_extension,
        confirmation_timeout_s=agent_spec.confirmation_timeout_s
    )