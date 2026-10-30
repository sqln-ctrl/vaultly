"""Run against a live local database: `pytest tests_smoke.py` (after migration)."""
import uuid
import logging

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


def test_password_reset_does_not_enumerate_accounts(caplog):
    unknown = f"missing-{uuid.uuid4()}@example.com"
    response = client.post("/api/v1/auth/forgot-password", json={"email": unknown})
    assert response.status_code == 202

    email = f"reset-{uuid.uuid4()}@example.com"
    assert client.post("/api/v1/auth/register", json={
        "email": email, "password": "password123", "full_name": "Reset Smoke",
    }).status_code == 201
    with caplog.at_level(logging.WARNING):
        assert client.post("/api/v1/auth/forgot-password", json={"email": email}).status_code == 202
    reset_link = next(
        record.getMessage().split("token=", 1)[1]
        for record in caplog.records
        if "Password reset link" in record.getMessage()
    )
    assert client.post("/api/v1/auth/reset-password", json={
        "token": reset_link, "password": "new-password456",
    }).status_code == 204
    assert client.post("/api/v1/auth/login", json={
        "email": email, "password": "new-password456",
    }).status_code == 200
    assert client.post("/api/v1/auth/reset-password", json={
        "token": reset_link, "password": "another-password",
    }).status_code == 400
