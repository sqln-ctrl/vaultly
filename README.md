# Vaultly

Secure document vault with an AI chatbot. React + FastAPI + PostgreSQL (pgvector).

## Run locally
```bash
# 1. Database, Redis and API (runs migrations automatically)
docker compose up --build

# 2. Frontend (new terminal)
cd frontend && npm install && npm run dev
```
- Web: http://localhost:5173
- API docs: http://localhost:8000/docs
- Email verification links are printed in the `api` container logs until an email provider is added.

## Phase 1 status (foundation)
Done: Docker stack, pgvector, Alembic, register/login/refresh (rotating, HttpOnly cookie)/logout/verify-email, React shell with protected routes.
Next: password reset email, rate limiting, then Phase 2 (upload to private storage, document list and detail).
