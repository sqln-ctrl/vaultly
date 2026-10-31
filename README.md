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
- By default, verification and password-reset links are printed in the `api` container logs. To send real email, configure Resend with `RESEND_API_KEY` and `EMAIL_FROM`.

### Configure Resend

1. Create a Resend API key.
2. Add `RESEND_API_KEY=re_xxx` to `backend/.env`.
3. Restart the API.

Before a sending domain is verified, use Resend's default `onboarding@resend.dev` sender. Resend restricts this sender to the email address associated with the account. Once a domain is verified, set `EMAIL_FROM=Vaultly <noreply@your-domain.com>`.

### Configure Google sign-in

1. Create an OAuth 2.0 Web Client ID in Google Cloud Console.
2. Add the allowed JavaScript origins used for the app, such as `http://localhost:5173`.
3. Set `GOOGLE_CLIENT_ID` in `backend/.env`.
4. Set the same client ID as `VITE_GOOGLE_CLIENT_ID` in `frontend/.env`.
5. Restart the frontend and API.

### Development-only manual verification

Leave `RESEND_API_KEY` empty to disable email delivery locally. Verify a local account from the backend directory:

```bash
cd backend
python verify_user.py user@example.com
```

This command is disabled automatically when `APP_ENV=production`.

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
Done: SQLite local stack, Alembic, register/login/refresh (rotating, HttpOnly cookie)/logout/verify-email, password reset, auth rate limiting, security response headers, React auth shell with protected routes.
Phase 2 status (documents)
Done: private per-user document storage, content-type validation, 15 MB and 20-page limits, duplicate SHA-256 detection, usage limits, library, detail, rename, delete, and 5-minute signed downloads.
Next: document processing and extracted fields.
