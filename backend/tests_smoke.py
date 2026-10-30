"""Run against a live local database: `pytest tests_smoke.py` (after migration)."""
import uuid
import logging
import base64
import fitz
from sqlalchemy import select

from fastapi.testclient import TestClient

from app.main import app
from app.db import SessionLocal
from app.models import User

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


def test_document_upload_duplicate_and_delete():
    email = f"documents-{uuid.uuid4()}@example.com"
    assert client.post("/api/v1/auth/register", json={
        "email": email, "password": "password123", "full_name": "Document Smoke",
    }).status_code == 201
    db = SessionLocal()
    user = db.scalar(select(User).where(User.email == email))
    user.email_verified = True
    db.commit()
    db.close()
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "password123"})
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
    )

    uploaded = client.post(
        "/api/v1/documents",
        headers=headers,
        files={"file": ("receipt.png", png, "image/png")},
    )
    assert uploaded.status_code == 201
    document_id = uploaded.json()["id"]

    duplicate = client.post(
        "/api/v1/documents",
        headers=headers,
        files={"file": ("copy.png", png, "image/png")},
    )
    assert duplicate.status_code == 409

    detail = client.get(f"/api/v1/documents/{document_id}", headers=headers)
    assert detail.status_code == 200
    signed = client.get(f"/api/v1/documents/{document_id}/download", headers=headers)
    assert signed.status_code == 200
    assert signed.json()["url"].startswith("/api/v1/documents/")
    assert client.delete(f"/api/v1/documents/{document_id}", headers=headers).status_code == 204


def test_pdf_upload_and_page_limit():
    email = f"pdf-{uuid.uuid4()}@example.com"
    assert client.post("/api/v1/auth/register", json={
        "email": email, "password": "password123", "full_name": "PDF Smoke",
    }).status_code == 201
    db = SessionLocal()
    user = db.scalar(select(User).where(User.email == email))
    user.email_verified = True
    db.commit()
    db.close()

    login = client.post("/api/v1/auth/login", json={"email": email, "password": "password123"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    pdf = fitz.open()
    pdf.new_page()
    pdf_bytes = pdf.tobytes()
    pdf.close()

    uploaded = client.post(
        "/api/v1/documents",
        headers=headers,
        files={"file": ("invoice.pdf", pdf_bytes, "application/pdf")},
    )
    assert uploaded.status_code == 201
    assert uploaded.json()["mime_type"] == "application/pdf"
    assert uploaded.json()["page_count"] == 1
