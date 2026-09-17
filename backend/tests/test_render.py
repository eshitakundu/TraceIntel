from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from app.config import Settings
from app.main import create_app
from fastapi.testclient import TestClient


@pytest.mark.parametrize("scheme", ["postgres://", "postgresql://", "postgresql+asyncpg://"])
def test_render_database_urls_are_normalized(scheme: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TRACEINTEL_DATABASE_URL", raising=False)
    monkeypatch.setenv("DATABASE_URL", scheme + "user:encoded%40password@db:5432/traceintel")
    settings = Settings(
        _env_file=None,
        environment="production",
        proxy_token="x" * 32,
    )
    assert settings.database_url.get_secret_value() == (
        "postgresql+asyncpg://user:encoded%40password@db:5432/traceintel"
    )
    assert "encoded%40password" not in repr(settings)


def test_readiness_checks_database_and_rejects_work_when_leases_fail() -> None:
    application = create_app(Settings(environment="test"))
    with TestClient(application) as client:
        assert client.get("/api/v1/ready").status_code == 200
        application.state.lease_healthy = False
        assert client.get("/api/v1/ready").status_code == 503
        response = client.post(
            "/api/v1/analyses",
            json={
                "chain": "ethereum",
                "transaction_hash": "0x" + "a" * 64,
            },
        )
        assert response.status_code == 503
        application.state.lease_healthy = True
        application.state.database = SimpleNamespace(
            connect=Mock(side_effect=RuntimeError("private-db-details"))
        )
        response = client.get("/api/v1/ready")
        assert response.status_code == 503
        assert "private-db-details" not in response.text
        assert client.get("/api/v1/health").status_code == 200
