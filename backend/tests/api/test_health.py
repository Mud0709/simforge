from fastapi.testclient import TestClient


def test_health_reports_versions(client: TestClient) -> None:
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert {"numpy_version", "scipy_version", "simforge_version"} <= body["environment"].keys()
