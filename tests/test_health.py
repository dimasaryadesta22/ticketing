def test_health_mengembalikan_200_dan_status_database(client):
    res = client.get("/health")
    assert res.status_code == 200
    body = res.get_json()
    assert body["status"] == "ok"
    assert body["database"] == "up"


def test_health_503_jika_database_tidak_bisa_diakses(tmp_path):
    from tiketin import create_app

    app = create_app({"TESTING": True, "DATABASE_URL": f"sqlite:///{tmp_path}/tidak/ada/db.sqlite"})
    res = app.test_client().get("/health")
    assert res.status_code == 503
    assert res.get_json()["database"] == "down"
