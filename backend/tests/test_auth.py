"""Tests for authentication endpoints."""


class TestRegister:
    def test_register_success(self, client):
        res = client.post("/api/auth/register", json={
            "name": "Ada Lovelace",
            "email": "ada@example.com",
            "password": "securepass",
        })
        assert res.status_code == 201
        data = res.get_json()
        assert "token" in data
        assert data["user"]["name"] == "Ada Lovelace"
        assert data["user"]["email"] == "ada@example.com"

    def test_register_duplicate_email(self, client, sample_user):
        res = client.post("/api/auth/register", json={
            "name": "Duplicate",
            "email": sample_user["email"],
            "password": "password123",
        })
        assert res.status_code == 409
        assert "already exists" in res.get_json()["error"]

    def test_register_missing_fields(self, client):
        res = client.post("/api/auth/register", json={
            "email": "missing@example.com",
        })
        assert res.status_code == 400

    def test_register_invalid_email(self, client):
        res = client.post("/api/auth/register", json={
            "name": "Bad Email",
            "email": "not-an-email",
            "password": "password123",
        })
        assert res.status_code == 400
        assert "valid email" in res.get_json()["error"]

    def test_register_short_password(self, client):
        res = client.post("/api/auth/register", json={
            "name": "Short Pass",
            "email": "short@example.com",
            "password": "ab",
        })
        assert res.status_code == 400
        assert "at least" in res.get_json()["error"]


class TestLogin:
    def test_login_success(self, client, sample_user):
        res = client.post("/api/auth/login", json={
            "email": sample_user["email"],
            "password": "password123",
        })
        assert res.status_code == 200
        data = res.get_json()
        assert "token" in data
        assert data["user"]["email"] == sample_user["email"]

    def test_login_wrong_password(self, client, sample_user):
        res = client.post("/api/auth/login", json={
            "email": sample_user["email"],
            "password": "wrongpassword",
        })
        assert res.status_code == 401

    def test_login_nonexistent_user(self, client):
        res = client.post("/api/auth/login", json={
            "email": "ghost@example.com",
            "password": "doesntmatter",
        })
        assert res.status_code == 401


class TestMe:
    def test_me_authenticated(self, client, auth_headers, sample_user):
        res = client.get("/api/auth/me", headers=auth_headers)
        assert res.status_code == 200
        assert res.get_json()["email"] == sample_user["email"]

    def test_me_unauthenticated(self, client):
        res = client.get("/api/auth/me")
        assert res.status_code == 401
