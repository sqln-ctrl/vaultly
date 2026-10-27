from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings

engine_options = {"pool_pre_ping": True}
if settings.database_url.startswith("sqlite"):
    # FastAPI handles requests in separate threads; SQLite requires this flag
    # for a single local database connection to be shared safely.
    engine_options["connect_args"] = {"check_same_thread": False}

engine = create_engine(settings.database_url, **engine_options)
SessionLocal = sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    with SessionLocal() as db:
        yield db
