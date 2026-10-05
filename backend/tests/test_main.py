from decimal import Decimal

from app.models import PayoutRun, RunStatus


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["version"] == "0.1.0"
    assert data["environment"] == "development"


def test_create_run(client):
    response = client.post("/runs", json={"budget_cap": "1000.00"})
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "DRAFT"
    assert data["budget_cap"] == "1000.00"
    assert data["sender_batch_id"].startswith("sp_")


def test_get_run(client):
    create_resp = client.post("/runs", json={"budget_cap": "500.00"})
    run_id = create_resp.json()["id"]

    response = client.get(f"/runs/{run_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == run_id
    assert data["budget_cap"] == "500.00"


def test_get_nonexistent_run(client):
    response = client.get("/runs/99999")
    assert response.status_code == 404


def test_list_runs(client):
    client.post("/runs", json={"budget_cap": "100.00"})
    client.post("/runs", json={"budget_cap": "200.00"})

    response = client.get("/runs")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 2


def test_run_model_creation(db_session):
    run = PayoutRun(
        budget_cap=Decimal("1000.00"),
        sender_batch_id="test_batch_123",
        status=RunStatus.DRAFT,
    )
    db_session.add(run)
    db_session.commit()

    assert run.id is not None
    assert run.budget_cap == Decimal("1000.00")
    assert run.status == RunStatus.DRAFT

