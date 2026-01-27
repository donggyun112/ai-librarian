import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock
from src.api.app import app
from src.auth.dependencies import get_user_scoped_client, verify_current_user
from src.auth.schemas import User

client = TestClient(app)


@pytest.fixture
def mock_supabase_client():
    """Mock Supabase AsyncClient"""
    mock = AsyncMock()
    mock.auth = AsyncMock()
    mock.table = MagicMock(return_value=mock)
    mock.select = MagicMock(return_value=mock)
    mock.insert = MagicMock(return_value=mock)
    mock.execute = AsyncMock()

    # Mock postgrest.auth() for user-scoped client
    mock.postgrest = MagicMock()
    mock.postgrest.auth = MagicMock()

    return mock


@pytest.fixture
def mock_current_user():
    """Mock authenticated user"""
    return User(
        id="user-123",
        aud="authenticated",
        role="authenticated",
        email="test@example.com",
        email_confirmed_at="2023-01-01T00:00:00Z",
        phone=None,
        confirmed_at="2023-01-01T00:00:00Z",
        last_sign_in_at="2023-01-01T00:00:00Z",
        app_metadata={"provider": "email"},
        user_metadata={},
        identities=[],
        created_at="2023-01-01T00:00:00Z",
        updated_at="2023-01-01T00:00:00Z",
    )


def test_get_books_without_auth():
    """Test GET /v1/books without authentication"""
    response = client.get("/v1/books")
    assert response.status_code == 401  # HTTPBearer auto_error returns 401


def test_get_books_success(mock_supabase_client, mock_current_user):
    """Test GET /v1/books with valid authentication"""
    app.dependency_overrides[get_user_scoped_client] = lambda: mock_supabase_client
    app.dependency_overrides[verify_current_user] = lambda: mock_current_user

    # Setup mock response
    mock_execute_response = MagicMock()
    mock_execute_response.data = [
        {
            "id": "book-1",
            "user_id": "user-123",
            "title": "Test Book 1",
            "created_at": "2023-01-01T00:00:00Z",
        },
        {
            "id": "book-2",
            "user_id": "user-123",
            "title": "Test Book 2",
            "created_at": "2023-01-02T00:00:00Z",
        },
    ]
    mock_supabase_client.execute.return_value = mock_execute_response

    response = client.get("/v1/books", headers={"Authorization": "Bearer valid_token"})

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["books"]) == 2
    assert data["books"][0]["title"] == "Test Book 1"
    assert data["books"][1]["title"] == "Test Book 2"

    app.dependency_overrides = {}


def test_get_books_empty(mock_supabase_client, mock_current_user):
    """Test GET /v1/books with no books"""
    app.dependency_overrides[get_user_scoped_client] = lambda: mock_supabase_client
    app.dependency_overrides[verify_current_user] = lambda: mock_current_user

    # Setup empty response
    mock_execute_response = MagicMock()
    mock_execute_response.data = []
    mock_supabase_client.execute.return_value = mock_execute_response

    response = client.get("/v1/books", headers={"Authorization": "Bearer valid_token"})

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert len(data["books"]) == 0

    app.dependency_overrides = {}


def test_create_book_without_auth():
    """Test POST /v1/books without authentication"""
    response = client.post("/v1/books", json={"title": "New Book"})
    assert response.status_code == 401  # HTTPBearer auto_error returns 401


def test_create_book_success(mock_supabase_client, mock_current_user):
    """Test POST /v1/books with valid authentication"""
    app.dependency_overrides[get_user_scoped_client] = lambda: mock_supabase_client
    app.dependency_overrides[verify_current_user] = lambda: mock_current_user

    # Setup mock response
    mock_execute_response = MagicMock()
    mock_execute_response.data = [
        {
            "id": "book-new",
            "user_id": "user-123",
            "title": "New Book",
            "created_at": "2023-01-03T00:00:00Z",
        }
    ]
    mock_supabase_client.execute.return_value = mock_execute_response

    response = client.post(
        "/v1/books",
        json={"title": "New Book"},
        headers={"Authorization": "Bearer valid_token"}
    )

    assert response.status_code == 201
    data = response.json()
    assert data["id"] == "book-new"
    assert data["user_id"] == "user-123"
    assert data["title"] == "New Book"

    app.dependency_overrides = {}


def test_create_book_validation_error(mock_supabase_client, mock_current_user):
    """Test POST /v1/books with invalid request body"""
    app.dependency_overrides[get_user_scoped_client] = lambda: mock_supabase_client
    app.dependency_overrides[verify_current_user] = lambda: mock_current_user

    response = client.post(
        "/v1/books",
        json={"title": ""},  # Empty title should fail validation
        headers={"Authorization": "Bearer valid_token"}
    )
    assert response.status_code == 422  # Pydantic validation error

    app.dependency_overrides = {}


def test_create_book_db_error(mock_supabase_client, mock_current_user):
    """Test POST /v1/books with database error"""
    app.dependency_overrides[get_user_scoped_client] = lambda: mock_supabase_client
    app.dependency_overrides[verify_current_user] = lambda: mock_current_user

    # Setup mock to return empty data (simulating insert failure)
    mock_execute_response = MagicMock()
    mock_execute_response.data = []
    mock_supabase_client.execute.return_value = mock_execute_response

    response = client.post(
        "/v1/books",
        json={"title": "New Book"},
        headers={"Authorization": "Bearer valid_token"}
    )

    assert response.status_code == 500
    assert "Failed to create book" in response.json()["detail"]

    app.dependency_overrides = {}
