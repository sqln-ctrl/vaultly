"""Development-only email verification helper."""
import sys

from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.models import User


def main() -> int:
    if settings.app_env.lower() == "production":
        print("Manual verification is disabled in production.")
        return 1
    if len(sys.argv) != 2:
        print("Usage: python verify_user.py <email>")
        return 1

    email = sys.argv[1].strip().lower()
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email))
        if not user:
            print(f"No account found for {email}")
            return 1
        if user.email_verified:
            print(f"{email} is already verified.")
            return 0
        user.email_verified = True
        db.commit()
    print(f"Verified {email}. You can sign in and upload documents now.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
