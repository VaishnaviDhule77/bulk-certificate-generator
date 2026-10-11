"""Shared pytest fixtures: per-test database and storage isolation."""

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from app import models  # noqa: F401  (import registers all ORM models)
from app.config import settings
from app.database import Base, get_session_factory
from app.main import app


def _create_engine_for(url: str) -> Engine:
    if url.startswith("sqlite"):
        return create_engine(url, connect_args={"check_same_thread": False})
    return create_engine(url)


@pytest.fixture()
def db_engine(tmp_path):
    """A fresh database with a clean schema for every single test."""
    url = os.environ.get("TEST_DATABASE_URL") or (
        f"sqlite+pysqlite:///{tmp_path / 'test.db'}"
    )
    engine = _create_engine_for(url)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def session_factory(db_engine):
    return sessionmaker(bind=db_engine, expire_on_commit=False)


@pytest.fixture()
def client(session_factory, tmp_path, monkeypatch):
    """API test client wired to the per-test database and a temp storage dir."""
    monkeypatch.setattr(settings, "output_dir", tmp_path / "certificates")
    app.dependency_overrides[get_session_factory] = lambda: session_factory
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_session_factory, None)