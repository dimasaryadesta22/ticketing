"""Lapisan database tipis yang mendukung PostgreSQL (produksi) dan SQLite (test).

Query ditulis dengan placeholder `?`; untuk PostgreSQL otomatis diubah menjadi `%s`.
`FOR UPDATE` hanya berlaku di PostgreSQL. Di SQLite, transaksi dibuka dengan
`BEGIN IMMEDIATE` yang mengunci database untuk penulisan, sehingga hasilnya sama:
pembelian tiket diproses satu per satu.
"""
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

from flask import current_app, g

try:  # driver PostgreSQL hanya diperlukan di produksi
    import psycopg
    from psycopg.rows import dict_row
except ImportError:  # pragma: no cover
    psycopg = None
    dict_row = None


class Connection:
    def __init__(self, url: str):
        self.url = url
        if url.startswith("sqlite:///"):
            self.dialect = "sqlite"
            path = url[len("sqlite:///"):]
            self._raw = sqlite3.connect(
                path, timeout=30, isolation_level=None, check_same_thread=False
            )
            self._raw.row_factory = sqlite3.Row
            self._raw.execute("PRAGMA foreign_keys = ON")
            self._raw.execute("PRAGMA busy_timeout = 30000")
            self.IntegrityError = sqlite3.IntegrityError
        elif url.startswith(("postgresql://", "postgres://")):
            if psycopg is None:
                raise RuntimeError("psycopg belum terpasang (pip install psycopg[binary])")
            self.dialect = "postgres"
            self._raw = psycopg.connect(url, autocommit=True, row_factory=dict_row)
            self.IntegrityError = psycopg.IntegrityError
        else:
            raise ValueError(f"DATABASE_URL tidak dikenali: {url}")
        self._in_tx = False

    # --- query -----------------------------------------------------------------
    def _sql(self, sql: str) -> str:
        if self.dialect == "postgres":
            return sql.replace("?", "%s")
        return sql.replace(" FOR UPDATE", "")

    def execute(self, sql: str, params=()):
        return self._raw.execute(self._sql(sql), tuple(params))

    def all(self, sql: str, params=()):
        return [dict(r) for r in self.execute(sql, params).fetchall()]

    def one(self, sql: str, params=()):
        # fetchall (bukan fetchone) agar statement INSERT/UPDATE ... RETURNING tuntas
        rows = self.all(sql, params)
        return rows[0] if rows else None

    def scalar(self, sql: str, params=()):
        row = self.one(sql, params)
        if row is None:
            return None
        return list(row.values())[0]

    # --- transaksi ---------------------------------------------------------------
    @contextmanager
    def transaction(self):
        if self._in_tx:  # transaksi bersarang ikut transaksi luar
            yield self
            return
        self._raw.execute("BEGIN IMMEDIATE" if self.dialect == "sqlite" else "BEGIN")
        self._in_tx = True
        try:
            yield self
        except BaseException:
            self._raw.execute("ROLLBACK")
            raise
        else:
            self._raw.execute("COMMIT")
        finally:
            self._in_tx = False

    def close(self):
        try:
            self._raw.close()
        except Exception:  # pragma: no cover
            pass


def get_db() -> Connection:
    if "db" not in g:
        g.db = Connection(current_app.config["DATABASE_URL"])
    return g.db


def close_db(_exc=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def connect_with_retry(url: str, attempts: int = 30, delay: float = 2.0) -> Connection:
    """Dipakai saat migrasi di entrypoint: tunggu database siap."""
    last = None
    for i in range(attempts):
        try:
            conn = Connection(url)
            conn.scalar("SELECT 1 AS ok")
            return conn
        except Exception as exc:  # pragma: no cover - tergantung jaringan
            last = exc
            print(f"[db] database belum siap ({i + 1}/{attempts}): {exc}", flush=True)
            time.sleep(delay)
    raise RuntimeError(f"Tidak bisa terhubung ke database: {last}")


# --- migrasi -----------------------------------------------------------------------
MIGRATIONS_DIR = Path(__file__).parent / "migrations"

_TYPES = {
    "postgres": {"PK": "SERIAL PRIMARY KEY", "TS": "TIMESTAMPTZ", "NOW": "NOW()"},
    "sqlite": {"PK": "INTEGER PRIMARY KEY AUTOINCREMENT", "TS": "TEXT", "NOW": "CURRENT_TIMESTAMP"},
}


def run_migrations(conn: Connection) -> list[str]:
    """Jalankan file migrations/*.sql yang belum pernah dijalankan, berurutan."""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        " version VARCHAR(100) PRIMARY KEY,"
        " applied_at VARCHAR(40) NOT NULL)"
    )
    applied = {r["version"] for r in conn.all("SELECT version FROM schema_migrations")}
    done = []
    for file in sorted(MIGRATIONS_DIR.glob("*.sql")):
        if file.stem in applied:
            continue
        sql = file.read_text(encoding="utf-8")
        for key, val in _TYPES[conn.dialect].items():
            sql = sql.replace("{" + key + "}", val)
        with conn.transaction():
            for statement in [s.strip() for s in sql.split(";") if s.strip()]:
                conn.execute(statement)
            conn.execute(
                "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
                (file.stem, time.strftime("%Y-%m-%dT%H:%M:%S")),
            )
        done.append(file.stem)
    return done
