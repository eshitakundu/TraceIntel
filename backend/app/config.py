from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TRACEINTEL_", env_file=".env", extra="ignore")

    environment: Literal["development", "test", "production"] = "development"
    cors_origins: list[str] = ["http://localhost:5173"]
    database_url: SecretStr = SecretStr("sqlite+aiosqlite:///./traceintel.db")
    ethereum_rpc_url: SecretStr = SecretStr("https://ethereum-rpc.publicnode.com")
    monad_rpc_url: SecretStr = SecretStr("https://rpc.monad.xyz")
    openrouter_api_key: SecretStr = SecretStr("")
    openrouter_model: str = ""
    rpc_timeout_seconds: float = Field(default=15, gt=0, le=60)
