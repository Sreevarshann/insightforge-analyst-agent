from __future__ import annotations

import json

from fastapi.testclient import TestClient

CSV = b"region,revenue\nEast,10\nWest,20\nEast,5\n"


def events(client: TestClient, question: str) -> list[dict]:  # type: ignore[type-arg]
    out = []
    with client.stream("POST", "/api/analyses/stream", json={"question": question}) as res:
        assert res.status_code == 200
        assert res.headers["content-type"].startswith("text/event-stream")
        for line in res.iter_lines():
            if line.startswith("data: "):
                out.append(json.loads(line[6:]))
    return out


def test_stream_emits_real_stage_events_in_order(client: TestClient) -> None:
    client.post("/api/datasets", files={"file": ("orders.csv", CSV)})
    evs = events(client, "total revenue by region")
    done_stages = [e["stage"] for e in evs if e["type"] == "stage" and e["status"] == "done"]
    assert done_stages == ["catalog", "plan", "validate", "execute", "inspect", "charts", "explain"]
    kinds = [e["type"] for e in evs]
    assert (
        kinds.index("result")
        < kinds.index("chart")
        < kinds.index("explanation")
        < kinds.index("done")
    )
    final = evs[-1]["analysis"]
    assert final["status"] == "completed"
    assert client.get(f"/api/analyses/{final['id']}").json()["id"] == final["id"]


def test_save_toggle_and_filter(client: TestClient) -> None:
    client.post("/api/datasets", files={"file": ("orders.csv", CSV)})
    a = client.post("/api/analyses", json={"question": "total revenue by region"}).json()
    assert client.patch(f"/api/analyses/{a['id']}", json={"saved": True}).json()["saved"] is True
    assert [x["id"] for x in client.get("/api/analyses?saved=true").json()] == [a["id"]]
