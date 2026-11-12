"""Seeder data contoh. Aman dijalankan berulang (tidak membuat data ganda)."""
from datetime import timedelta

from werkzeug.security import generate_password_hash

from . import clock
from .db import Connection

DEMO_BUYER = ("Pembeli Demo", "pembeli@tiketin.local", "pembeli123")

SAMPLE_EVENTS = [
    # (nama, hari dari sekarang, harga, kuota)
    ("Konser Kampus: Malam Puncak Dies Natalis", 30, 75000, 200),
    ("Seminar Nasional DevOps & Cloud", 14, 50000, 100),
    ("Workshop Docker untuk Pemula", 7, 25000, 20),
]


def _ensure_user(conn: Connection, name: str, email: str, password: str, is_admin: bool) -> str:
    if conn.one("SELECT id FROM users WHERE email = ?", (email,)):
        return "ada"
    conn.execute(
        "INSERT INTO users (name, email, password_hash, is_admin) VALUES (?, ?, ?, ?)",
        (name, email, generate_password_hash(password), is_admin),
    )
    return "dibuat"


def run_seed(conn: Connection, admin_email: str, admin_password: str, today=None) -> list[str]:
    today = today or clock.today()
    log = [
        f"admin {admin_email}: {_ensure_user(conn, 'Admin Tiketin', admin_email, admin_password, True)}",
        f"user {DEMO_BUYER[1]}: {_ensure_user(conn, *DEMO_BUYER, False)}",
    ]
    for name, days, price, quota in SAMPLE_EVENTS:
        if conn.one("SELECT id FROM events WHERE name = ?", (name,)):
            log.append(f"event '{name}': ada")
            continue
        conn.execute(
            "INSERT INTO events (name, event_date, price, quota) VALUES (?, ?, ?, ?)",
            (name, (today + timedelta(days=days)).isoformat(), price, quota),
        )
        log.append(f"event '{name}': dibuat")
    return log
