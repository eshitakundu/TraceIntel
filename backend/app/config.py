from typing import Literal, Self

from pydantic import AliasChoices, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TRACEINTEL_", env_file=".env", extra="ignore", populate_by_name=True
    )

    environment: Literal["development", "test", "production"] = "development"
    cors_origins: list[str] = ["http://localhost:5173"]
    database_url: SecretStr = SecretStr("sqlite+aiosqlite:///./traceintel.db")
    ethereum_rpc_url: SecretStr = SecretStr("https://ethereum-rpc.publicnode.com")
    monad_rpc_url: SecretStr = SecretStr("https://rpc.monad.xyz")
    openrouter_api_key: SecretStr = Field(
        default=SecretStr(""),
        validation_alias=AliasChoices("OPENROUTER_API_KEY", "TRACEINTEL_OPENROUTER_API_KEY"),
    )
    openrouter_model: str = Field(
        default="", validation_alias=AliasChoices("OPENROUTER_MODEL", "TRACEINTEL_OPENROUTER_MODEL")
    )
    rpc_timeout_seconds: float = Field(default=15, gt=0, le=60)

    explorer_api_key: SecretStr = SecretStr("")
    traces_enabled: bool = False
    max_concurrent_analyses: int = Field(default=2, ge=1, le=8)
    requests_per_hour: int = Field(default=20, ge=1, le=1000)
    daily_analyses: int = Field(default=100, ge=1, le=10000)
    daily_llm_analyses: int = Field(default=20, ge=0, le=1000)

    proxy_token: SecretStr = SecretStr("")

    @model_validator(mode="after")
    def production_requirements(self) -> Self:
        if self.environment == "production":
            if not self.database_url.get_secret_value().startswith("postgresql+asyncpg://"):
                raise ValueError("Production requires PostgreSQL persistence.")
            if len(self.proxy_token.get_secret_value()) < 32:
                raise ValueError("Production requires a proxy token of at least 32 characters.")
        return self
