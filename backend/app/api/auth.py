import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..models import RefreshToken, User
from ..schemas import AuthOut, LoginIn, RegisterIn, UserOut, VerifyIn
from ..security import (
    create_token, decode_token, hash_password, hash_token, new_refresh_token, verify_password,
)
from .deps import current_user

router = APIRouter(prefix="/auth", tags=["auth"])
log = logging.getLogger("vaultly.auth")
COOKIE = "refresh_token"
COOKIE_PATH = "/api/v1/auth"


def _as_utc(value: datetime) -> datetime:
    """Normalize SQLite's naive timestamps and PostgreSQL's aware ones."""
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _issue(db: Session, user: User, response: Response) -> AuthOut:
    raw, hashed = new_refresh_token()
    expires = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_days)
    db.add(RefreshToken(user_id=user.id, token_hash=hashed, expires_at=expires))
    db.commit()
    response.set_cookie(
        COOKIE, raw, httponly=True, secure=settings.cookie_secure, samesite="lax",
        max_age=settings.refresh_token_days * 86400, path=COOKIE_PATH,
    )
    access = create_token(str(user.id), "access", settings.access_token_minutes)
    return AuthOut(access_token=access, user=UserOut.model_validate(user))


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    email = body.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")
    user = User(email=email, password_hash=hash_password(body.password), full_name=body.full_name.strip())
    db.add(user)
    db.commit()
    token = create_token(str(user.id), "verify", settings.verify_token_minutes)
    # TODO(Phase 1b): send via email provider. Logged for local development.
    log.warning("Verify link for %s: %s/verify-email?token=%s", email, settings.frontend_url, token)
    return user


@router.post("/verify-email", status_code=status.HTTP_204_NO_CONTENT)
def verify_email(body: VerifyIn, db: Session = Depends(get_db)):
    sub = decode_token(body.token, "verify")
    user = db.get(User, uuid.UUID(sub)) if sub else None
    if not user:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This verification link is invalid or expired")
    user.email_verified = True
    db.commit()


@router.post("/login", response_model=AuthOut)
def login(body: LoginIn, response: Response, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if not user or not verify_password(user.password_hash, body.password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Email or password is incorrect")
    return _issue(db, user, response)


@router.post("/refresh", response_model=AuthOut)
def refresh(response: Response, db: Session = Depends(get_db), refresh_token: str | None = Cookie(None)):
    if not refresh_token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sign in to continue")
    row = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_token(refresh_token)))
    now = datetime.now(timezone.utc)
    if not row or row.revoked_at or _as_utc(row.expires_at) < now:
        response.delete_cookie(COOKIE, path=COOKIE_PATH)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired. Sign in again")
    row.revoked_at = now  # rotate: each refresh token works once
    user = db.get(User, row.user_id)
    return _issue(db, user, response)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response, db: Session = Depends(get_db), refresh_token: str | None = Cookie(None)):
    if refresh_token:
        row = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_token(refresh_token)))
        if row and not row.revoked_at:
            row.revoked_at = datetime.now(timezone.utc)
            db.commit()
    response.delete_cookie(COOKIE, path=COOKIE_PATH)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user
