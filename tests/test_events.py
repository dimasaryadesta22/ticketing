from datetime import timedelta

from tiketin import clock


def test_admin_bisa_crud_event(client, admin, create_event):
    ev = create_event(quota=50, name="Seminar AI")
    assert ev["available"] == 50

    res = client.put(f"/api/events/{ev['id']}", json={"price": 60000}, headers=admin)
    assert res.status_code == 200
    assert res.get_json()["event"]["price"] == 60000

    assert client.get(f"/api/events/{ev['id']}").status_code == 200
    assert client.delete(f"/api/events/{ev['id']}", headers=admin).status_code == 204
    assert client.get(f"/api/events/{ev['id']}").status_code == 404


def test_pembeli_biasa_tidak_boleh_membuat_event(client, make_user):
    res = client.post(
        "/api/events",
        json={"name": "X", "event_date": (clock.today() + timedelta(days=3)).isoformat(), "price": 0, "quota": 5},
        headers=make_user(),
    )
    assert res.status_code == 403


def test_validasi_input_event(client, admin):
    besok = (clock.today() + timedelta(days=1)).isoformat()
    kemarin = (clock.today() - timedelta(days=1)).isoformat()
    for bad in (
        {"name": "", "event_date": besok, "price": 0, "quota": 5},
        {"name": "A", "event_date": "31-12-2026", "price": 0, "quota": 5},
        {"name": "A", "event_date": kemarin, "price": 0, "quota": 5},
        {"name": "A", "event_date": besok, "price": -1, "quota": 5},
        {"name": "A", "event_date": besok, "price": 0, "quota": 0},
    ):
        assert client.post("/api/events", json=bad, headers=admin).status_code == 422, bad


def test_kuota_tidak_bisa_diturunkan_di_bawah_tiket_terjual(client, admin, make_user, create_event):
    ev = create_event(quota=10)
    client.post(f"/api/events/{ev['id']}/tickets", json={"quantity": 3}, headers=make_user())
    res = client.put(f"/api/events/{ev['id']}", json={"quota": 2}, headers=admin)
    assert res.status_code == 409
    assert res.get_json()["error"]["code"] == "QUOTA_BELOW_SOLD"
