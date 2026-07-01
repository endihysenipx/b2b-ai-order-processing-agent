from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings

engine_kwargs = {"pool_pre_ping": True}
if settings.database_url.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
    if settings.database_url == "sqlite://":
        engine_kwargs["poolclass"] = StaticPool

engine = create_engine(settings.database_url, **engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
