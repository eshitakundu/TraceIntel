import json
import time
from pathlib import Path

import httpx
from app.config import Settings
from app.main import create_app
from app.models.blockchain import RawTransaction
from fastapi.testclient import TestClient


def test_validation_and_report_lifecycle() -> None:
    raw = RawTransaction.model_validate_json(Path("evals/cases/ethereum-recorded.json").read_text())
    values = {
        "eth_chainId": "0x1",
        "eth_getTransactionByHash": json.loads(raw.transaction_json),
        "eth_getTransactionReceipt": json.loads(raw.receipt_json),
        "eth_getBlockByNumber": json.loads(raw.block_json),
        "eth_getCode": "0x",
        "eth_call": "0x",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        return httpx.Response(200, json={"id": body["id"], "result": values[body["method"]]})

    app = create_app(Settings(openrouter_api_key="", openrouter_model=""))
    with TestClient(app) as client:
        app.state.analysis.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        assert (
            client.post(
                "/api/v1/analyses", json={"chain": "ethereum", "transaction_hash": "bad"}
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/api/v1/analyses", json={"chain": "unsupported", "transaction_hash": raw.tx_hash}
            ).status_code
            == 422
        )
        response = client.post(
            "/api/v1/analyses", json={"chain": "ethereum", "transaction_hash": raw.tx_hash}
        )
        assert response.status_code == 202
        job = response.json()
        for _ in range(100):
            job = client.get(f"/api/v1/analyses/{job['id']}").json()
            if job["status"] in ("complete", "failed"):
                break
            time.sleep(0.02)
        assert job["status"] == "complete", job
        report = client.get(f"/api/v1/reports/{job['report_id']}").json()
        assert report["transaction_hash"] == raw.tx_hash
        assert report["interpretation"]["status"] == "unavailable"
        evidence_ids = {e["id"] for e in report["decoded"]["evidence"]}
        assert all(
            set(signal["evidence_ids"]) <= evidence_ids for signal in report["risk"]["signals"]
        )
        repeated = client.post(
            "/api/v1/analyses", json={"chain": "ethereum", "transaction_hash": raw.tx_hash}
        ).json()
        assert repeated["id"] == job["id"]
        downloaded = client.get(f"/api/v1/reports/{job['id']}/download")
        assert downloaded.json() == report
        assert "attachment" in downloaded.headers["content-disposition"]
        values["eth_getBlockByNumber"]["hash"] = "0x" + "c" * 64
        refreshed = client.post(
            "/api/v1/analyses", json={"chain": "ethereum", "transaction_hash": raw.tx_hash}
        ).json()
        assert refreshed["id"] != job["id"]
        assert client.get(f"/api/v1/reports/{job['id']}").status_code == 200
