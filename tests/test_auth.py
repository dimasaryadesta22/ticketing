def test_register_login_dan_me(client):
    res = client.post(
        "/api/auth/register",
        json={"name": "Budi", "email": "budi@kampus.ac.id", "password": "rahasia123"},
    )
    assert res.status_code == 201

    res = client.post("/api/auth/login", json={"email": "budi@kampus.ac.id", "password": "rahasia123"})
    assert res.status_code == 200
    token = res.get_json()["token"]

    res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.get_json()["user"]["email"] == "budi@kampus.ac.id"


def test_email_ganda_dan_password_salah_ditolak(client):
    payload = {"name": "Sari", "email": "sari@kampus.ac.id", "password": "rahasia123"}
    assert client.post("/api/auth/register", json=payload).status_code == 201
    assert client.post("/api/auth/register", json=payload).status_code == 409

    res = client.post("/api/auth/login", json={"email": "sari@kampus.ac.id", "password": "salah-sekali"})
    assert res.status_code == 401


def test_endpoint_tiket_wajib_login(client):
    assert client.get("/api/tickets/me").status_code == 401
