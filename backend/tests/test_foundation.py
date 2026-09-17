import pytest
from app.config import Settings
from app.main import create_app
from fastapi.testclient import TestClient
from pydantic import ValidationError


def test_health_and_openapi() -> None:
    with TestClient(create_app(Settings(environment="test"))) as client:
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "service": "traceintel-api", "version": "0.1.0"}
        assert "/api/v1/health" in client.get("/openapi.json").json()["paths"]


def test_cors_is_explicit() -> None:
    with TestClient(create_app()) as client:
        accepted = client.get("/api/v1/health", headers={"Origin": "http://localhost:5173"})
        assert accepted.headers["access-control-allow-origin"] == "http://localhost:5173"
        denied = client.get("/api/v1/health", headers={"Origin": "https://untrusted.example"})
        assert "access-control-allow-origin" not in denied.headers


def test_settings_validate_and_mask_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRACEINTEL_OPENROUTER_API_KEY", "test-secret")
    settings = Settings()
    assert "test-secret" not in repr(settings)
    with pytest.raises(ValidationError):
        Settings(rpc_timeout_seconds=0)


def test_public_chain_registry_preserves_both_supported_networks() -> None:
    with TestClient(create_app(Settings(environment="test"))) as client:
        response = client.get("/api/v1/chains")
        assert response.status_code == 200
        payload = response.json()
        assert {chain["slug"]: chain["chain_id"] for chain in payload} == {
            "ethereum": 1,
            "monad": 143,
        }
        assert all("rpc_url" not in chain for chain in payload)
