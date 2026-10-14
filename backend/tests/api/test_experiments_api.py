from fastapi.testclient import TestClient

SIM = "/api/v1/physics/projectile/simulate"


def test_saved_run_is_listed_and_retrievable(client: TestClient) -> None:
    run = client.post(SIM, json={"parameters": {"mass": 2.5}}).json()
    run_id = run["metadata"]["run_id"]

    listed = client.get("/api/v1/experiments").json()
    assert [e["run_id"] for e in listed] == [run_id]

    record = client.get(f"/api/v1/experiments/{run_id}").json()
    assert record["inputs"]["parameters"]["mass"] == 2.5
    assert record["input_hash"] == run["metadata"]["input_hash"]
    assert record["summary"]["analytical"]["range"] == run["analytical"]["range"]
    assert record["environment"]["numpy_version"] == run["metadata"]["numpy_version"]


def test_unsaved_run_is_not_recorded(client: TestClient) -> None:
    client.post(SIM, json={"save_experiment": False})
    assert client.get("/api/v1/experiments").json() == []


def test_list_is_newest_first_and_filterable(client: TestClient) -> None:
    ids = [client.post(SIM, json={}).json()["metadata"]["run_id"] for _ in range(3)]
    listed = client.get("/api/v1/experiments", params={"limit": 2}).json()
    assert [e["run_id"] for e in listed] == ids[::-1][:2]
    assert client.get("/api/v1/experiments", params={"model_id": "nope"}).json() == []


def test_unknown_experiment_is_404(client: TestClient) -> None:
    assert client.get("/api/v1/experiments/does-not-exist").status_code == 404
