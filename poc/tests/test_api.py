from fastapi.testclient import TestClient
from src.api.app import app

client = TestClient(app)

def test_health_check():
    """Test the /health endpoint returns 200 OK and correct status."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
