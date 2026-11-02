def test_public_info_of_brazilian_salon(db_client):
    response = db_client.get("/t/alpha")

    assert response.status_code == 200
    assert response.json() == {
        "slug": "alpha",
        "name": "Salão Alpha",
        "country": "BR",
        "locale": "pt-BR",
        "timezone": "America/Sao_Paulo",
        "currency": "BRL",
    }


def test_public_info_of_paraguayan_salon(db_client):
    body = db_client.get("/t/beta").json()

    assert (body["locale"], body["timezone"], body["currency"]) == ("es", "America/Asuncion", "PYG")


def test_public_info_has_no_personal_data(db_client):
    assert "dono@" not in db_client.get("/t/alpha").text


def test_unknown_salon(db_client):
    response = db_client.get("/t/nao-existe")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "tenant_not_found"


def test_readiness_with_real_database(db_client):
    assert db_client.get("/health/ready").json() == {"status": "ok", "database": "ok"}
