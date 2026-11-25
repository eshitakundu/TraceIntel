from typing import Literal, Self

from pydantic import AliasChoices, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TRACEINTEL_", env_file=".env", extra="ignore", populate_by_name=True
    )

    environment: Literal["development", "test", "production"] = "development"
    cors_origins: list[str] = ["http://localhost:5173"]
    database_url: SecretStr = Field(
        default=SecretStr("sqlite+aiosqlite:///./traceintel.db"),
        validation_alias=AliasChoices("TRACEINTEL_DATABASE_URL", "DATABASE_URL"),
    )
    # Drift detection compares the spender at the approval block with today, which needs
    # archive state. dRPC's free Ethereum endpoint serves it; most public RPCs prune it.
    ethereum_rpc_url: SecretStr = SecretStr("https://eth.drpc.org")
    monad_rpc_url: SecretStr = SecretStr("https://rpc.monad.xyz")
    openrouter_api_key: SecretStr = Field(
        default=SecretStr(""),
        validation_alias=AliasChoices("OPENROUTER_API_KEY", "TRACEINTEL_OPENROUTER_API_KEY"),
    )
    openrouter_model: str = Field(
        default="", validation_alias=AliasChoices("OPENROUTER_MODEL", "TRACEINTEL_OPENROUTER_MODEL")
    )
    # Which hosted model API to use. OpenRouter stays the default; "nvidia_nim" uses NVIDIA's
    # API catalog (build.nvidia.com) through LiteLLM's nvidia_nim provider.
    llm_provider: Literal["openrouter", "nvidia_nim"] = Field(
        default="openrouter",
        validation_alias=AliasChoices("LLM_PROVIDER", "TRACEINTEL_LLM_PROVIDER"),
    )
    nvidia_api_key: SecretStr = Field(
        default=SecretStr(""),
        validation_alias=AliasChoices(
            "NVIDIA_API_KEY", "NVIDIA_NIM_API_KEY", "TRACEINTEL_NVIDIA_API_KEY"
        ),
    )
    nvidia_model: str = Field(
        default="", validation_alias=AliasChoices("NVIDIA_MODEL", "TRACEINTEL_NVIDIA_MODEL")
    )
    rpc_timeout_seconds: float = Field(default=15, gt=0, le=60)

    explorer_api_key: SecretStr = SecretStr("")
    traces_enabled: bool = False
    max_concurrent_analyses: int = Field(default=2, ge=1, le=8)
    requests_per_hour: int = Field(default=20, ge=1, le=1000)
    daily_analyses: int = Field(default=100, ge=1, le=10000)
    daily_llm_analyses: int = Field(default=20, ge=0, le=1000)

    proxy_token: SecretStr = SecretStr("")

    @property
    def llm_model(self) -> str:
        return self.nvidia_model if self.llm_provider == "nvidia_nim" else self.openrouter_model

    @property
    def llm_api_key(self) -> str:
        key = self.nvidia_api_key if self.llm_provider == "nvidia_nim" else self.openrouter_api_key
        return key.get_secret_value()

    @property
    def llm_enabled(self) -> bool:
        return bool(self.llm_api_key and self.llm_model)

    @property
    def llm_route(self) -> str:
        """The LiteLLM model string, for example "nvidia_nim/meta/llama-3.3-70b-instruct"."""
        return f"{self.llm_provider}/{self.llm_model}"

    @model_validator(mode="after")
    def production_requirements(self) -> Self:
        url = self.database_url.get_secret_value()
        for prefix in ("postgres://", "postgresql://"):
            if url.startswith(prefix):
                self.database_url = SecretStr("postgresql+asyncpg://" + url[len(prefix) :])
                break
        if self.environment == "production":
            if not self.database_url.get_secret_value().startswith("postgresql+asyncpg://"):
                raise ValueError("Production requires PostgreSQL persistence.")
            if len(self.proxy_token.get_secret_value()) < 32:
                raise ValueError("Production requires a proxy token of at least 32 characters.")
        return self
