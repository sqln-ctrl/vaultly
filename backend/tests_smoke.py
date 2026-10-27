"""Run against a live local database: `pytest tests_smoke.py` (after migration)."""
import uuid

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_auth_flow():
    email = f"smoke-{uuid.uuid4()}@example.com"
    register = client.post("/api/v1/auth/register", json={"email": email, "password": "password123", "full_name": "Smoke"})
    assert register.status_code == 201
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "password123"})
    assert r.status_code == 200
    token = r.json()["access_token"]
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 200
    assert client.post("/api/v1/auth/refresh").status_code == 200
    assert client.post("/api/v1/auth/login", json={"email": email, "password": "wrong"}).status_code == 401
