"""Fixture test. Test memakai SQLite file sementara sehingga bisa jalan di dalam
container `test` tanpa perlu service database."""
import pytest

from tiketin import create_app
from tiketin.db import Connection, run_migrations


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
