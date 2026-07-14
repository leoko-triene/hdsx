from fastapi.testclient import TestClient

from app.main import app


def test_live_health_does_not_require_external_services():
    response = TestClient(app).get("/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

