import json
from unittest.mock import patch

import pytest

from app.config import Config


@pytest.fixture
def alerts_client(api_client, tmp_path):
    """Isola alerts.json num arquivo temporário — nunca toca no alerts.json
    real do projeto durante os testes."""
    client, conn = api_client
    alerts_path = tmp_path / "alerts_test.json"
    alerts_path.write_text("[]", encoding="utf-8")

    test_config = Config(alerts_file=str(alerts_path))
    with patch("app.api.routers.alerts.get_config", return_value=test_config):
        yield client, conn, alerts_path


def test_list_alerts_empty_by_default(alerts_client):
    client, _, _ = alerts_client
    response = client.get("/api/v1/alerts")
    assert response.status_code == 200
    assert response.json() == []


def test_create_alert_persists_to_file_and_db(alerts_client):
    client, conn, alerts_path = alerts_client
    response = client.post("/api/v1/alerts", json={
        "name": "Possível BUG geral", "any": ["bug"], "bug_mode": True,
    })
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Possível BUG geral"
    assert data["id"] is not None

    file_content = json.loads(alerts_path.read_text(encoding="utf-8"))
    assert len(file_content) == 1
    assert file_content[0]["name"] == "Possível BUG geral"

    db_row = conn.execute("SELECT * FROM alerts WHERE name = ?", ("Possível BUG geral",)).fetchone()
    assert db_row is not None


def test_create_alert_rejects_duplicate_name(alerts_client):
    client, _, _ = alerts_client
    client.post("/api/v1/alerts", json={"name": "Notebook", "required": ["notebook"]})
    response = client.post("/api/v1/alerts", json={"name": "Notebook", "required": ["notebook"]})
    assert response.status_code == 400


def test_update_alert_changes_fields(alerts_client):
    client, _, alerts_path = alerts_client
    created = client.post("/api/v1/alerts", json={"name": "Notebook", "min_score": 0}).json()

    response = client.put(f"/api/v1/alerts/{created['id']}", json={
        "name": "Notebook", "min_score": 70, "max_price": 4500,
    })
    assert response.status_code == 200
    assert response.json()["min_score"] == 70
    assert response.json()["max_price"] == 4500

    file_content = json.loads(alerts_path.read_text(encoding="utf-8"))
    assert file_content[0]["min_score"] == 70


def test_update_alert_404_when_missing(alerts_client):
    client, _, _ = alerts_client
    response = client.put("/api/v1/alerts/9999", json={"name": "X"})
    assert response.status_code == 404


def test_toggle_alert_flips_enabled(alerts_client):
    client, _, _ = alerts_client
    created = client.post("/api/v1/alerts", json={"name": "Notebook", "enabled": True}).json()

    response = client.post(f"/api/v1/alerts/{created['id']}/toggle")
    assert response.json()["enabled"] is False

    response2 = client.post(f"/api/v1/alerts/{created['id']}/toggle")
    assert response2.json()["enabled"] is True


def test_delete_alert_removes_from_file_but_keeps_db_history(alerts_client):
    client, conn, alerts_path = alerts_client
    created = client.post("/api/v1/alerts", json={"name": "Notebook"}).json()

    response = client.delete(f"/api/v1/alerts/{created['id']}")
    assert response.status_code == 200
    assert response.json() == {"deleted": True, "name": "Notebook"}

    file_content = json.loads(alerts_path.read_text(encoding="utf-8"))
    assert file_content == []

    # historico preservado no banco (promocoes antigas continuam com FK valida)
    db_row = conn.execute("SELECT * FROM alerts WHERE name = ?", ("Notebook",)).fetchone()
    assert db_row is not None

    assert client.get("/api/v1/alerts").json() == []
