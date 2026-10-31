import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from google.auth.transport.requests import Request
from google.oauth2 import id_token

from ..config import settings
from ..db import get_db
from ..models import PasswordResetToken, RefreshToken, User
from ..schemas import (
    AuthOut, ForgotPasswordIn, GoogleLoginIn, LoginIn, RegisterIn, ResendVerificationIn, ResetPasswordIn, UserOut, VerifyIn,
)
from ..security import (
    create_token, decode_token, hash_password, hash_token, new_refresh_token, verify_password,
)
from .deps import current_user
from ..email import send_email

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
async def register(body: RegisterIn, db: Session = Depends(get_db)):
    email = body.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")
    user = User(email=email, password_hash=hash_password(body.password), full_name=body.full_name.strip())
    db.add(user)
    db.commit()
    token = create_token(str(user.id), "verify", settings.verify_token_minutes)
    log.warning("Verify link for %s: %s/verify-email?token=%s", email, settings.frontend_url, token)
    await send_email(
        to=email,
        subject="Verify your Vaultly email",
        text=f"Verify your email: {settings.frontend_url}/verify-email?token={token}",
        html=f'<p>Verify your Vaultly account:</p><p><a href="{settings.frontend_url}/verify-email?token={token}">Verify email</a></p>',
    )
    return user


@router.post("/verify-email", status_code=status.HTTP_204_NO_CONTENT)
def verify_email(body: VerifyIn, db: Session = Depends(get_db)):
    sub = decode_token(body.token, "verify")
    user = db.get(User, uuid.UUID(sub)) if sub else None
    if not user:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This verification link is invalid or expired")
    user.email_verified = True
    db.commit()


@router.post("/resend-verification", status_code=status.HTTP_202_ACCEPTED)
async def resend_verification(body: ResendVerificationIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if user and not user.email_verified:
        token = create_token(str(user.id), "verify", settings.verify_token_minutes)
        link = f"{settings.frontend_url}/verify-email?token={token}"
        log.warning("Verify link for %s: %s", user.email, link)
        await send_email(
            to=user.email,
            subject="Verify your Vaultly email",
            text=f"Verify your email: {link}",
            html=f'<p>Verify your Vaultly account:</p><p><a href="{link}">Verify email</a></p>',
        )
    return {"message": "If the account exists and is unverified, a new verification link has been sent"}


@router.post("/login", response_model=AuthOut)
def login(body: LoginIn, response: Response, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if not user or not verify_password(user.password_hash, body.password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Email or password is incorrect")
    return _issue(db, user, response)


@router.post("/google", response_model=AuthOut)
def google_login(body: GoogleLoginIn, response: Response, db: Session = Depends(get_db)):
    if not settings.google_client_id:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Google sign-in is not configured")
    try:
        claims = id_token.verify_oauth2_token(
            body.credential,
            Request(),
            audience=settings.google_client_id,
        )
    except ValueError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Google sign-in could not be verified")

    google_sub = claims.get("sub")
    email = claims.get("email", "").lower()
    email_verified = claims.get("email_verified") is True
    if not google_sub or not email or not email_verified:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "A verified Google account is required")

    user = db.scalar(select(User).where(User.google_sub == google_sub))
    if user is None:
        user = db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(
            email=email,
            password_hash=None,
            google_sub=google_sub,
            full_name=str(claims.get("name") or email.split("@", 1)[0]).strip()[:120],
            email_verified=True,
        )
        db.add(user)
    else:
        user.google_sub = google_sub
        user.email_verified = True
    db.commit()
    db.refresh(user)
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


@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)
async def forgot_password(body: ForgotPasswordIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if user:
        raw, hashed = new_refresh_token()
        expires = datetime.now(timezone.utc) + timedelta(minutes=settings.reset_token_minutes)
        db.query(PasswordResetToken).filter(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None),
        ).update({PasswordResetToken.used_at: datetime.now(timezone.utc)})
        db.add(PasswordResetToken(user_id=user.id, token_hash=hashed, expires_at=expires))
        db.commit()
        log.warning(
            "Password reset link for %s: %s/reset-password?token=%s",
            user.email, settings.frontend_url, raw,
        )
        link = f"{settings.frontend_url}/reset-password?token={raw}"
        await send_email(
            to=user.email,
            subject="Reset your Vaultly password",
            text=f"Reset your password: {link}",
            html=f'<p>Reset your Vaultly password:</p><p><a href="{link}">Reset password</a></p><p>This link expires in {settings.reset_token_minutes} minutes.</p>',
        )
    # Always return the same response so account existence cannot be enumerated.
    return {"message": "If an account exists for that email, a reset link has been sent"}


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(body: ResetPasswordIn, db: Session = Depends(get_db)):
    row = db.scalar(select(PasswordResetToken).where(
        PasswordResetToken.token_hash == hash_token(body.token),
    ))
    now = datetime.now(timezone.utc)
    if not row or row.used_at or _as_utc(row.expires_at) < now:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This reset link is invalid or expired")
    user = db.get(User, row.user_id)
    if not user:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This reset link is invalid or expired")
    user.password_hash = hash_password(body.password)
    row.used_at = now
    db.query(RefreshToken).filter(
        RefreshToken.user_id == user.id,
        RefreshToken.revoked_at.is_(None),
    ).update({RefreshToken.revoked_at: now})
    db.commit()


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user
