from typing import Literal

from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    status: Literal["ok"] = "ok"
    service: Literal["traceintel-api"] = "traceintel-api"
    version: str = "0.1.0"
