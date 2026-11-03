"""SAL-05: serviços com nome, preço (na moeda do salão) e duração; ativar e desativar."""

import uuid

import pytest
from sqlalchemy import text

from app.core.infra.db import Databases
from app.core.infra.tenancy import load_tenant, tenant_session
from tests.test_auth import access_token, bearer


@pytest.fixture
def owner_token(db_client, make_user):
    return access_token(db_client, make_user("alpha", role="owner"))


def _create(client, token, slug="alpha", **overrides):
    body = {"name": f"Hidratação {uuid.uuid4().hex[:4]}", "duration_min": 40, "price_minor": 7590,
            **overrides}  # fmt: skip
    return client.post(f"/t/{slug}/services", json=body, headers=bearer(token))


def _list(client, token, slug="alpha", **params):
    response = client.get(f"/t/{slug}/services", params=params, headers=bearer(token))
    assert response.status_code == 200, response.text
    return response.json()


# --- serviços de exemplo (SAL-01) --------------------------------------------------------


def test_new_brazilian_salon_comes_with_sample_services_in_reais(db_client, owner_token):
    services = {s["name"]: s for s in _list(db_client, owner_token)}

    assert services["Corte feminino"]["price_minor"] == 8000
    assert services["Corte feminino"]["duration_min"] == 60
    assert services["Corte feminino"]["currency"] == "BRL"
    assert {"Manicure", "Barba", "Coloração"} <= set(services)


def test_new_paraguayan_salon_comes_with_sample_services_in_guaranis(db_client, make_user):
    token = access_token(db_client, make_user("beta", role="owner"))

    services = {s["name"]: s for s in _list(db_client, token, slug="beta")}

    assert services["Corte de dama"]["price_minor"] == 80_000
    assert services["Corte de dama"]["currency"] == "PYG"
    assert "Manicura" in services


# --- cadastro ----------------------------------------------------------------------------


def test_owner_creates_a_service(db_client, owner_token):
    response = _create(db_client, owner_token, name="  Hidratação  ")

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Hidratação"
    assert (body["duration_min"], body["price_minor"], body["currency"]) == (40, 7590, "BRL")
    assert body["is_active"] is True


@pytest.mark.parametrize(
    ("overrides", "field", "code"),
    [
        ({"duration_min": 0}, "duration_min", "invalid_duration"),
        ({"duration_min": 42}, "duration_min", "invalid_duration"),
        ({"duration_min": 485}, "duration_min", "invalid_duration"),
        ({"price_minor": -1}, "price_minor", "invalid_price"),
        ({"price_minor": 100_000_001}, "price_minor", "invalid_price"),
        ({"name": "  "}, "name", "string_too_short"),
    ],
)
def test_invalid_service(db_client, owner_token, overrides, field, code):
    response = _create(db_client, owner_token, **overrides)

    assert response.status_code == 422
    assert response.json()["error"]["fields"][0] == {"field": field, "code": code}


def test_free_service_is_allowed(db_client, owner_token):
    assert _create(db_client, owner_token, price_minor=0).status_code == 201


def test_change_price_duration_and_name(db_client, owner_token):
    service = _create(db_client, owner_token).json()

    response = db_client.patch(
        f"/t/alpha/services/{service['id']}",
        json={"price_minor": 9900, "duration_min": 50},
        headers=bearer(owner_token),
    )

    body = response.json()
    assert (body["price_minor"], body["duration_min"], body["name"]) == (9900, 50, service["name"])


def test_deactivated_service_leaves_the_default_list(db_client, owner_token):
    service = _create(db_client, owner_token).json()

    db_client.patch(
        f"/t/alpha/services/{service['id']}", json={"is_active": False}, headers=bearer(owner_token)
    )

    active_ids = {s["id"] for s in _list(db_client, owner_token)}
    all_ids = {s["id"] for s in _list(db_client, owner_token, include_inactive=True)}
    assert service["id"] not in active_ids
    assert service["id"] in all_ids


def test_list_is_alphabetical(db_client, owner_token):
    names = [s["name"] for s in _list(db_client, owner_token)]

    assert names == sorted(names)


def test_service_of_another_salon_is_not_found(db_client, owner_token, make_user):
    service = _create(db_client, owner_token).json()
    beta = access_token(db_client, make_user("beta", role="owner"))

    response = db_client.patch(
        f"/t/beta/services/{service['id']}", json={"price_minor": 1}, headers=bearer(beta)
    )

    assert response.status_code == 404


def test_everyone_on_the_team_can_see_services_but_only_the_owner_edits(db_client, make_user):
    for role in ("reception", "professional"):
        token = access_token(db_client, make_user("alpha", role=role))
        assert db_client.get("/t/alpha/services", headers=bearer(token)).status_code == 200
        assert _create(db_client, token).status_code == 403


def test_price_lives_in_the_salon_table_and_offering_in_the_core(
    db_settings, db_client, owner_token
):
    """Separação do template: a agenda (core) não sabe de preço."""
    service = _create(db_client, owner_token).json()
    databases = Databases(db_settings)

    with tenant_session(databases, load_tenant(databases, "alpha")) as session:
        offering_columns = set(session.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 't_alpha' AND table_name = 'offerings'"
        )).scalars())  # fmt: skip
        price = session.execute(
            text("SELECT price_minor FROM salon_service_prices WHERE offering_id = :id"),
            {"id": service["id"]},
        ).scalar()

    assert "price_minor" not in offering_columns
    assert price == 7590
