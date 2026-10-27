# Vaultly

Secure document vault with an AI chatbot. React + FastAPI + SQLite for local development.

## Run locally
```bash
# 1. API with a persistent SQLite database (runs migrations automatically)
docker compose up --build

# 2. Frontend (new terminal)
cd frontend && npm install && npm run dev
```
- Web: http://localhost:5173
- API docs: http://localhost:8000/docs
- Email verification links are printed in the `api` container logs until an email provider is added.

### Run without Docker

Use Python 3.12 and run the backend from its directory. The default `DATABASE_URL`
creates `backend/vaultly.db`, which is intentionally not committed.

```bash
cd backend
python -m venv .venv
# Activate .venv for your shell, then:
python -m pip install -r requirements.txt
alembic upgrade head
python -m uvicorn app.main:app --reload
```

## Later: PostgreSQL/Supabase

The data model and Alembic migration use portable UUID types. When ready to
migrate, provision PostgreSQL (for example, Supabase), set `DATABASE_URL` to
its SQLAlchemy URL (such as `postgresql+psycopg://...`), and run `alembic
upgrade head`. The pgvector extension is created only on PostgreSQL.

## Phase 1 status (foundation)
Done: SQLite local stack, Alembic, register/login/refresh (rotating, HttpOnly cookie)/logout/verify-email, React shell with protected routes.
Next: password reset email, rate limiting, then Phase 2 (upload to private storage, document list and detail).
