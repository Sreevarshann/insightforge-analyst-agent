from __future__ import annotations

from fastapi.testclient import TestClient

CSV = b"id,region,revenue\n1,East,10\n2,West,20\n3,East,5\n"


def _seed(client: TestClient) -> None:
    assert client.post("/api/datasets", files={"file": ("orders.csv", CSV)}).status_code == 201


def test_executes_valid_query_and_logs(client: TestClient) -> None:
    _seed(client)
    res = client.post(
        "/api/query",
        json={"sql": "SELECT region, sum(revenue) r FROM orders GROUP BY 1 ORDER BY 1"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["rows"] == [["East", 15], ["West", 20]]
    assert body["tables"] == ["orders"] and len(body["dataset_versions"]) == 1
    hist = client.get("/api/query/history").json()
    assert hist[0]["accepted"] and hist[0]["row_count"] == 2


def test_rejected_query_is_logged_with_reason(client: TestClient) -> None:
    _seed(client)
    res = client.post("/api/query", json={"sql": "DROP TABLE orders"})
    assert res.status_code == 422 and res.json()["detail"]["kind"] == "rejected"
    hist = client.get("/api/query/history").json()
    assert not hist[0]["accepted"] and "read-only" in hist[0]["rejection_reason"]


def test_runtime_error_is_reported_without_internals(client: TestClient, settings) -> None:  # type: ignore[no-untyped-def]
    _seed(client)
    res = client.post("/api/query", json={"sql": "SELECT no_such_col FROM orders"})
    assert res.status_code == 400 and res.json()["detail"]["kind"] == "execution"
    assert str(settings.data_dir) not in res.text


def test_max_rows_respected(client: TestClient) -> None:
    _seed(client)
    body = client.post("/api/query", json={"sql": "SELECT * FROM orders", "max_rows": 2}).json()
    assert len(body["rows"]) == 2 and body["truncated"]
