"""Aturan bisnis Tiketin. Semua validasi penting dilakukan di sini, di sisi server.

Aturan yang diuji:
1. Tiket terjual tidak boleh melebihi kuota, termasuk saat banyak pembelian bersamaan.
   -> baris event dikunci (SELECT ... FOR UPDATE) di dalam transaksi, jadi pembelian
      pada event yang sama diproses bergantian. Constraint CHECK (sold <= quota) di
      database menjadi pengaman terakhir.
2. Satu akun maksimal 4 tiket (aktif) per event.
3. Pembatalan hanya sebelum H-1 dan mengembalikan kuota.
"""
import secrets
from datetime import date, timedelta

from flask import current_app

from . import clock
from .db import Connection
from .errors import BusinessRuleError, NotFound, ValidationError

_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # tanpa O/0/I/1 agar tidak tertukar


# --- helper ----------------------------------------------------------------------
def to_date(value) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def to_iso(value):
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def new_ticket_code() -> str:
    return "TKT-" + "".join(secrets.choice(_CODE_ALPHABET) for _ in range(8))


def serialize_event(ev: dict) -> dict:
    return {
        "id": ev["id"],
        "name": ev["name"],
        "event_date": to_iso(to_date(ev["event_date"])),
        "price": ev["price"],
        "quota": ev["quota"],
        "sold": ev["sold"],
        "available": ev["quota"] - ev["sold"],
    }


def serialize_ticket(t: dict) -> dict:
    data = {
        "code": t["code"],
        "status": t["status"],
        "event_id": t["event_id"],
        "purchased_at": to_iso(t.get("purchased_at")),
        "cancelled_at": to_iso(t.get("cancelled_at")),
    }
    if "event_name" in t:
        data["event"] = {
            "id": t["event_id"],
            "name": t["event_name"],
            "event_date": to_iso(to_date(t["event_date"])),
            "price": t["price"],
        }
    return data


# --- validasi input event ----------------------------------------------------------
def validate_event_payload(payload: dict, partial: bool = False) -> dict:
    if not isinstance(payload, dict):
        raise ValidationError("Body harus berupa JSON object")
    clean = {}

    if "name" in payload or not partial:
        name = str(payload.get("name") or "").strip()
        if not name or len(name) > 150:
            raise ValidationError("Nama event wajib diisi (maks. 150 karakter)")
        clean["name"] = name

    if "event_date" in payload or not partial:
        try:
            ev_date = date.fromisoformat(str(payload.get("event_date")))
        except ValueError:
            raise ValidationError("Tanggal event wajib berformat YYYY-MM-DD")
        if ev_date < clock.today():
            raise ValidationError("Tanggal event tidak boleh di masa lalu")
        clean["event_date"] = ev_date.isoformat()

    for field, minimum, label in (("price", 0, "Harga"), ("quota", 1, "Kuota")):
        if field in payload or not partial:
            value = payload.get(field)
            if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
                raise ValidationError(f"{label} harus bilangan bulat >= {minimum}")
            clean[field] = value

    if partial and not clean:
        raise ValidationError("Tidak ada field yang diubah")
    return clean


# --- event ---------------------------------------------------------------------------
def list_events(conn: Connection) -> list[dict]:
    rows = conn.all("SELECT * FROM events ORDER BY event_date, id")
    return [serialize_event(r) for r in rows]


def get_event(conn: Connection, event_id: int) -> dict:
    ev = conn.one("SELECT * FROM events WHERE id = ?", (event_id,))
    if ev is None:
        raise NotFound("Event tidak ditemukan")
    return ev


def create_event(conn: Connection, payload: dict) -> dict:
    data = validate_event_payload(payload)
    row = conn.one(
        "INSERT INTO events (name, event_date, price, quota) VALUES (?, ?, ?, ?) RETURNING *",
        (data["name"], data["event_date"], data["price"], data["quota"]),
    )
    return serialize_event(row)


def update_event(conn: Connection, event_id: int, payload: dict) -> dict:
    data = validate_event_payload(payload, partial=True)
    with conn.transaction():
        ev = conn.one("SELECT * FROM events WHERE id = ? FOR UPDATE", (event_id,))
        if ev is None:
            raise NotFound("Event tidak ditemukan")
        if "quota" in data and data["quota"] < ev["sold"]:
            raise BusinessRuleError(
                "QUOTA_BELOW_SOLD",
                f"Kuota tidak boleh lebih kecil dari tiket yang sudah terjual ({ev['sold']})",
            )
        sets = ", ".join(f"{k} = ?" for k in data)
        row = conn.one(
            f"UPDATE events SET {sets} WHERE id = ? RETURNING *", (*data.values(), event_id)
        )
    return serialize_event(row)


def delete_event(conn: Connection, event_id: int, force: bool = False) -> None:
    with conn.transaction():
        ev = conn.one("SELECT * FROM events WHERE id = ? FOR UPDATE", (event_id,))
        if ev is None:
            raise NotFound("Event tidak ditemukan")
        if ev["sold"] > 0 and not force:
            raise BusinessRuleError(
                "EVENT_HAS_TICKETS", "Event yang sudah memiliki tiket terjual tidak dapat dihapus"
            )
        conn.execute("DELETE FROM tickets WHERE event_id = ?", (event_id,))
        conn.execute("DELETE FROM events WHERE id = ?", (event_id,))


# --- tiket ---------------------------------------------------------------------------
def purchase_tickets(conn: Connection, user_id: int, event_id: int, quantity) -> list[dict]:
    max_per_account = current_app.config["MAX_TICKETS_PER_ACCOUNT"]
    if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity < 1:
        raise ValidationError("Jumlah tiket (quantity) harus bilangan bulat >= 1")
    if quantity > max_per_account:
        raise BusinessRuleError(
            "LIMIT_PER_ACCOUNT", f"Satu akun maksimal {max_per_account} tiket per event"
        )

    with conn.transaction():
        # Kunci baris event: pembelian lain pada event ini menunggu sampai transaksi selesai.
        ev = conn.one("SELECT * FROM events WHERE id = ? FOR UPDATE", (event_id,))
        if ev is None:
            raise NotFound("Event tidak ditemukan")
        if to_date(ev["event_date"]) < clock.today():
            raise BusinessRuleError("EVENT_PASSED", "Event sudah berlalu")

        owned = conn.scalar(
            "SELECT COUNT(*) AS n FROM tickets WHERE event_id = ? AND user_id = ? AND status = 'ACTIVE'",
            (event_id, user_id),
        )
        if owned + quantity > max_per_account:
            raise BusinessRuleError(
                "LIMIT_PER_ACCOUNT",
                f"Satu akun maksimal {max_per_account} tiket per event "
                f"(sudah punya {owned}, sisa jatah {max_per_account - owned})",
            )

        available = ev["quota"] - ev["sold"]
        if quantity > available:
            raise BusinessRuleError(
                "SOLD_OUT" if available == 0 else "QUOTA_EXCEEDED",
                "Tiket habis" if available == 0 else f"Sisa kuota hanya {available} tiket",
            )

        tickets = []
        for _ in range(quantity):
            tickets.append(
                conn.one(
                    "INSERT INTO tickets (code, event_id, user_id) VALUES (?, ?, ?) RETURNING *",
                    (new_ticket_code(), event_id, user_id),
                )
            )
        conn.execute("UPDATE events SET sold = sold + ? WHERE id = ?", (quantity, event_id))

    return [serialize_ticket(t) for t in tickets]


def list_user_tickets(conn: Connection, user_id: int) -> list[dict]:
    rows = conn.all(
        "SELECT t.*, e.name AS event_name, e.event_date, e.price "
        "FROM tickets t JOIN events e ON e.id = t.event_id "
        "WHERE t.user_id = ? ORDER BY t.id DESC",
        (user_id,),
    )
    return [serialize_ticket(r) for r in rows]


def get_ticket(conn: Connection, code: str, user: dict) -> dict:
    row = conn.one(
        "SELECT t.*, e.name AS event_name, e.event_date, e.price "
        "FROM tickets t JOIN events e ON e.id = t.event_id WHERE t.code = ?",
        (code,),
    )
    if row is None or (row["user_id"] != user["id"] and not user["is_admin"]):
        raise NotFound("Tiket tidak ditemukan")
    return serialize_ticket(row)


def cancel_ticket(conn: Connection, user_id: int, code: str) -> dict:
    ticket = conn.one("SELECT * FROM tickets WHERE code = ?", (code,))
    if ticket is None or ticket["user_id"] != user_id:
        raise NotFound("Tiket tidak ditemukan")

    with conn.transaction():
        ev = conn.one("SELECT * FROM events WHERE id = ? FOR UPDATE", (ticket["event_id"],))
        ticket = conn.one("SELECT * FROM tickets WHERE code = ? FOR UPDATE", (code,))
        if ticket["status"] != "ACTIVE":
            raise BusinessRuleError("ALREADY_CANCELLED", "Tiket sudah dibatalkan")

        deadline = to_date(ev["event_date"]) - timedelta(
            days=current_app.config["CANCEL_DEADLINE_DAYS"]
        )
        if clock.today() >= deadline:
            raise BusinessRuleError(
                "CANCEL_DEADLINE_PASSED",
                f"Pembatalan hanya bisa dilakukan sebelum H-1 (paling lambat {to_iso(deadline - timedelta(days=1))})",
            )

        row = conn.one(
            "UPDATE tickets SET status = 'CANCELLED', cancelled_at = ? WHERE code = ? RETURNING *",
            (clock.now().isoformat(), code),
        )
        # Pembatalan mengembalikan kuota.
        conn.execute("UPDATE events SET sold = sold - 1 WHERE id = ?", (ev["id"],))
    return serialize_ticket(row)
