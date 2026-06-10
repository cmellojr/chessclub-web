"""Test fixtures and configuration for chessclub-web."""

from collections.abc import Generator

import pytest
from flask import Flask
from flask.testing import FlaskClient
from flask_sqlalchemy import SQLAlchemy

from app import create_app


@pytest.fixture
def app(monkeypatch: pytest.MonkeyPatch) -> Generator[Flask, None, None]:
    """Create a Flask app configured for testing with an in-memory database."""
    monkeypatch.setattr("app.sync.init_scheduler", lambda app: None)
    app = create_app()
    app.config.update({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "SQLALCHEMY_ENGINE_OPTIONS": {
            "connect_args": {"check_same_thread": False},
        },
        "ADMIN_PASSWORD": "test-password",
    })
    with app.app_context():
        from app.extensions import db

        db.create_all()
    yield app


@pytest.fixture
def client(app: Flask) -> FlaskClient:
    """Create a Flask test client."""
    return app.test_client()


@pytest.fixture
def db(app: Flask) -> Generator[SQLAlchemy, None, None]:
    """Provide the SQLAlchemy database instance within an app context."""
    with app.app_context():
        from app.extensions import db as _db

        yield _db
        _db.session.rollback()


@pytest.fixture
def club_in_db(app: Flask) -> None:
    """Insert a test club into the database for route tests."""
    with app.app_context():
        from chessclub.core.models import Club

        from app.db_service import upsert_club

        upsert_club(
            Club(
                id="test-club",
                provider_id="123",
                name="Test Club",
                description="A test club",
                country="US",
                url="https://chess.com/club/test-club",
                members_count=10,
                created_at=1600000000,
                location="Testville",
                matches_count=5,
            )
        )
