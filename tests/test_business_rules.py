"""Test aturan bisnis Tiketin (K02)."""
import threading
from datetime import date, timedelta

from tiketin import clock


def buy(client, event_id, headers, quantity=1):
    return client.post(f"/api/events/{event_id}/tickets", json={"quantity": quantity}, headers=headers)


def sold(client, event_id):
    return client.get(f"/api/events/{event_id}").get_json()["event"]["sold"]


# --- Aturan 1: tiket terjual tidak boleh melebihi kuota -----------------------------
def test_tiket_terjual_tidak_boleh_melebihi_kuota(client, make_user, create_event):
    ev = create_event(quota=5)
    assert buy(client, ev["id"], make_user(), 4).status_code == 201

    res = buy(client, ev["id"], make_user(), 2)  # sisa 1, minta 2
    assert res.status_code == 409
    assert res.get_json()["error"]["code"] == "QUOTA_EXCEEDED"

    assert buy(client, ev["id"], make_user(), 1).status_code == 201
    res = buy(client, ev["id"], make_user(), 1)
    assert res.status_code == 409
    assert res.get_json()["error"]["code"] == "SOLD_OUT"
    assert sold(client, ev["id"]) == 5


def test_pembelian_bersamaan_tidak_overselling(app, make_user, create_event):
    """50 pembeli berbeda membeli bersamaan pada event berkuota 20 -> tepat 20 berhasil."""
    ev = create_event(quota=20)
    users = [make_user() for _ in range(50)]
    start = threading.Barrier(len(users))
    results = []
    lock = threading.Lock()

    def worker(headers):
        client = app.test_client()
        start.wait()
        status = buy(client, ev["id"], headers).status_code
        with lock:
            results.append(status)

    threads = [threading.Thread(target=worker, args=(u,)) for u in users]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert results.count(201) == 20
    assert results.count(409) == 30
    assert sold(app.test_client(), ev["id"]) == 20


# --- Aturan 2: satu akun maksimal 4 tiket per event -------------------------------------
def test_satu_akun_maksimal_4_tiket_per_event(client, make_user, create_event):
    ev = create_event(quota=100)
    user = make_user()

    res = buy(client, ev["id"], user, 5)  # langsung 5 sekaligus
    assert res.status_code == 409
    assert res.get_json()["error"]["code"] == "LIMIT_PER_ACCOUNT"

    assert buy(client, ev["id"], user, 3).status_code == 201
    assert buy(client, ev["id"], user, 2).status_code == 409  # 3 + 2 = 5
    assert buy(client, ev["id"], user, 1).status_code == 201  # total 4
    assert buy(client, ev["id"], user, 1).status_code == 409  # yang ke-5

    # batas berlaku per event: event lain tetap boleh
    ev2 = create_event(quota=100, name="Event Lain")
    assert buy(client, ev2["id"], user, 4).status_code == 201


def test_setiap_tiket_punya_kode_unik(client, make_user, create_event):
    ev = create_event(quota=50)
    codes = []
    for _ in range(5):
        res = buy(client, ev["id"], make_user(), 4)
        codes += [t["code"] for t in res.get_json()["tickets"]]
    assert len(codes) == 20
    assert len(set(codes)) == 20
    assert all(c.startswith("TKT-") and len(c) == 12 for c in codes)


# --- Aturan 3: pembatalan sebelum H-1 & mengembalikan kuota -----------------------------
def test_pembatalan_mengembalikan_kuota(client, make_user, create_event):
    ev = create_event(quota=2)
    user = make_user()
    code = buy(client, ev["id"], user, 2).get_json()["tickets"][0]["code"]
    assert buy(client, ev["id"], make_user(), 1).get_json()["error"]["code"] == "SOLD_OUT"

    res = client.post(f"/api/tickets/{code}/cancel", headers=user)
    assert res.status_code == 200
    assert res.get_json()["ticket"]["status"] == "CANCELLED"
    assert sold(client, ev["id"]) == 1

    # kuota yang dikembalikan bisa dibeli orang lain
    assert buy(client, ev["id"], make_user(), 1).status_code == 201
    # tiket yang sama tidak bisa dibatalkan dua kali
    assert client.post(f"/api/tickets/{code}/cancel", headers=user).status_code == 409


def test_pembatalan_hanya_sebelum_h_minus_1(client, make_user, create_event, monkeypatch):
    ev = create_event(quota=10, days_ahead=10)
    event_date = date.fromisoformat(ev["event_date"])
    user = make_user()
    codes = [t["code"] for t in buy(client, ev["id"], user, 2).get_json()["tickets"]]

    # H-1: ditolak
    monkeypatch.setattr(clock, "today", lambda: event_date - timedelta(days=1))
    res = client.post(f"/api/tickets/{codes[0]}/cancel", headers=user)
    assert res.status_code == 409
    assert res.get_json()["error"]["code"] == "CANCEL_DEADLINE_PASSED"

    # Hari-H: ditolak
    monkeypatch.setattr(clock, "today", lambda: event_date)
    assert client.post(f"/api/tickets/{codes[0]}/cancel", headers=user).status_code == 409

    # H-2: masih boleh
    monkeypatch.setattr(clock, "today", lambda: event_date - timedelta(days=2))
    assert client.post(f"/api/tickets/{codes[0]}/cancel", headers=user).status_code == 200
    assert sold(client, ev["id"]) == 1


def test_tidak_bisa_membatalkan_tiket_orang_lain(client, make_user, create_event):
    ev = create_event(quota=5)
    code = buy(client, ev["id"], make_user(), 1).get_json()["tickets"][0]["code"]
    assert client.post(f"/api/tickets/{code}/cancel", headers=make_user()).status_code == 404
    assert sold(client, ev["id"]) == 1
