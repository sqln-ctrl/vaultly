import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import User
from ..security import decode_token

bearer = HTTPBearer(auto_error=False)


def current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    sub = decode_token(creds.credentials, "access") if creds else None
    user = db.get(User, uuid.UUID(sub)) if sub else None
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sign in to continue")
    return user


def verified_user(user: User = Depends(current_user)) -> User:
    """Use on upload and chat routes (Phase 2+)."""
    if not user.email_verified:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Verify your email first")
    return user
