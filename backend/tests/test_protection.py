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


def test_ipv6_clients_share_a_slash_64_bucket() -> None:
    from app.api.routes.analysis import client_bucket

    assert client_bucket("203.0.113.7") == "203.0.113.7"
    assert client_bucket("2001:db8:1:2::1") == client_bucket("2001:db8:1:2:ffff::9")
    assert client_bucket("2001:db8:1:2::1") != client_bucket("2001:db8:1:3::1")
    assert client_bucket("unknown") == "unknown"
