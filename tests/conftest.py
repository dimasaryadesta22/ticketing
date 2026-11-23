"""Fixture test. Test memakai SQLite file sementara sehingga bisa jalan di dalam
container `test` tanpa perlu service database."""
import itertools
from datetime import timedelta

import pytest
from werkzeug.security import generate_password_hash

from tiketin import clock, create_app
from tiketin.auth import issue_token
from tiketin.db import Connection, run_migrations

_counter = itertools.count(1)


@pytest.fixture()
def app(tmp_path):
    url = f"sqlite:///{tmp_path / 'test.db'}"
    conn = Connection(url)
    run_migrations(conn)
    conn.close()
    app = create_app({"TESTING": True, "DATABASE_URL": url, "SECRET_KEY": "test-secret"})
    yield app


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def db(app):
    conn = Connection(app.config["DATABASE_URL"])
    yield conn
    conn.close()


@pytest.fixture()
def make_user(app, db):
    """Buat user langsung di database, kembalikan header Authorization-nya."""

    def _make(is_admin: bool = False) -> dict:
        n = next(_counter)
        row = db.one(
            "INSERT INTO users (name, email, password_hash, is_admin) VALUES (?, ?, ?, ?) RETURNING id",
            (f"User {n}", f"user{n}@test.local", generate_password_hash("x", method="pbkdf2:sha256:1"), is_admin),
        )
        with app.app_context():
            token = issue_token(row["id"])
        return {"Authorization": f"Bearer {token}"}

    return _make


@pytest.fixture()
def admin(make_user):
    return make_user(is_admin=True)


@pytest.fixture()
def create_event(client, admin):
    def _create(quota: int = 10, days_ahead: int = 30, price: int = 50000, name: str = "Event Test") -> dict:
        event_date = (clock.today() + timedelta(days=days_ahead)).isoformat()
        res = client.post(
            "/api/events",
            json={"name": name, "event_date": event_date, "price": price, "quota": quota},
            headers=admin,
        )
        assert res.status_code == 201, res.get_json()
        return res.get_json()["event"]

    return _create
