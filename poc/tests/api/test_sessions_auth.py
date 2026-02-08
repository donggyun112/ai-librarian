from fastapi.testclient import TestClient
from src.api.app import app

client = TestClient(app)


def test_create_session_requires_auth():
    response = client.post("/v1/sessions")
    assert response.status_code == 401


def test_list_sessions_requires_auth():
    response = client.get("/v1/sessions")
    assert response.status_code == 401


def test_session_detail_requires_auth():
    response = client.get("/v1/sessions/test-session")
    assert response.status_code == 401


def test_send_message_requires_auth():
    response = client.post(
        "/v1/sessions/test-session/messages",
        json={"message": "hello", "stream": False},
    )
    assert response.status_code == 401


def test_delete_session_requires_auth():
    response = client.delete("/v1/sessions/test-session")
    assert response.status_code == 401
