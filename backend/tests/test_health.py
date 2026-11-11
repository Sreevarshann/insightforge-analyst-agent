from __future__ import annotations

from fastapi.testclient import TestClient

from insightforge.config import Settings


def test_health_reports_status_and_provider(client: TestClient) -> None:
    res = client.get("/api/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["environment"] == "test"
    assert body["llm_provider"] == "fixture"


def test_startup_creates_data_directories(client: TestClient, settings: Settings) -> None:
    assert settings.datasets_dir.is_dir()


def test_unknown_route_returns_404(client: TestClient) -> None:
    assert client.get("/api/does-not-exist").status_code == 404


def test_startup_runs_migrations(client: TestClient, settings: Settings) -> None:
    assert settings.metadata_db_path.is_file()
