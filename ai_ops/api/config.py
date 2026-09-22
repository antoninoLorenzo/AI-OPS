from functools import lru_cache

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from ai_ops.config import (
    API_BASE_ENV_NAME,
    API_KEY_ENV_NAME,
)
from ai_ops.core.log import get_logger
from ai_ops.core.storage import StorageStrategy

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

