"""Database engine, session management, and FastAPI dependencies."""

from collections.abc import Iterator

from fastapi import Depends
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    """Base class for all ORM models (SQLAlchemy 2.x declarative style)."""


engine = create_engine(settings.database_url, pool_pre_ping=True)

# expire_on_commit=False lets us read attributes (e.g. job.id) after committing.
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_session_factory() -> sessionmaker[Session]:
    """Return the application-wide session factory.

    Background tasks cannot reuse the request's session (it closes once the
    response is sent), so they receive this factory and open their own session.
    """
    return SessionLocal


def get_db(
    session_factory: sessionmaker[Session] = Depends(get_session_factory),
) -> Iterator[Session]:
    """FastAPI dependency providing a request-scoped database session."""
    with session_factory() as session:
        yield session