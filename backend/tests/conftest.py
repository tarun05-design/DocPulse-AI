"""
Pytest fixtures for DocPulse AI backend tests.
Uses SQLite in-memory database and mocks external services.
"""
import pytest
from unittest.mock import patch

from app import create_app
from app.config import TestingConfig
from app.extensions import db as _db
from app.models import User


@pytest.fixture(scope="session")
def app():
    """Create the Flask app with testing config."""
    application = create_app(TestingConfig)
    yield application


@pytest.fixture(scope="function")
def db(app):
    """Create fresh tables for each test."""
    with app.app_context():
        _db.create_all()
        yield _db
        _db.session.rollback()
        _db.drop_all()


@pytest.fixture()
def client(app, db):
    """Flask test client."""
    return app.test_client()


@pytest.fixture()
def sample_user(app, db):
    """Create and return a sample user."""
    with app.app_context():
        user = User(name="Test User", email="test@example.com")
        user.set_password("password123")
        db.session.add(user)
        db.session.commit()
        return {"id": user.id, "name": user.name, "email": user.email}


@pytest.fixture()
def auth_headers(client, sample_user):
    """Get JWT auth headers for the sample user."""
    res = client.post("/api/auth/login", json={
        "email": sample_user["email"],
        "password": "password123",
    })
    token = res.get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def mock_blob_storage():
    """Mock blob storage for all tests to avoid Azure calls."""
    with patch("app.services.blob_storage._use_azure", return_value=False), \
         patch("app.services.blob_storage._local_upload", return_value=("test.pdf", "local://test.pdf")), \
         patch("app.services.blob_storage._local_download", return_value=b"fake pdf content"), \
         patch("app.services.blob_storage._local_delete"):
        yield
