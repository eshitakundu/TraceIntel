import pytest
from app.config import Settings
from app.main import create_app
from fastapi.testclient import TestClient
from pydantic import ValidationError


def test_production_rejects_sqlite_and_missing_proxy_secret() -> None:
    with pytest.raises(ValidationError, match="PostgreSQL"):
        Settings(environment="production", database_url="sqlite+aiosqlite:///local.db")
    with pytest.raises(ValidationError, match="proxy token"):
        Settings(
            environment="production", database_url="postgresql+asyncpg://test/db", proxy_token=""
        )


def test_oversized_requests_do_not_start_jobs() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/api/v1/analyses", content="x" * 4097)
        assert response.status_code == 413
