"""SAL-04: clientes com consentimento, e auditoria de quem criou, viu ou alterou."""

import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError, ProgrammingError
from sqlalchemy.pool import NullPool

from app.core.infra.db import Databases
from app.core.infra.tenancy import load_tenant, tenant_session
from app.core.tenants.provisioning import migrate_tenants
from tests.test_auth import access_token, bearer


@pytest.fixture
def reception(db_client, make_user):
    user = make_user("alpha", role="reception")
    return user, access_token(db_client, user)


@pytest.fixture
def owner_token(db_client, make_user):
    return access_token(db_client, make_user("alpha", role="owner"))


def _create(client, token, slug="alpha", **overrides):
    body = {
        "name": "Maria Silva",
        "phone": "(11) 98888-7777",
        "email": "Maria@Exemplo.com",
        "consents": ["service", "reminders"],
        **overrides,
    }
    return client.post(f"/t/{slug}/customers", json=body, headers=bearer(token))


def _audit(client, token, entity_id, slug="alpha"):
    response = client.get(
        f"/t/{slug}/audit", params={"entity_id": entity_id}, headers=bearer(token)
    )
    assert response.status_code == 200, response.text
    return response.json()


# --- cadastro e consentimento ------------------------------------------------------------


def test_create_customer_normalizes_phone_and_records_consent(db_client, reception):
    user, token = reception

    response = _create(db_client, token)

    assert response.status_code == 201
    body = response.json()
    assert body["phone"] == "+5511988887777"
    assert body["phone_display"] == "+55 11 98888-7777"
    assert body["email"] == "maria@exemplo.com"
    assert {c["purpose"] for c in body["consents"]} == {"service", "reminders"}
    assert all(c["source"] == "staff" for c in body["consents"])
    assert body["consents"][0]["policy_version"] == "2026-11-02"


def test_paraguayan_phone_uses_the_salon_country(db_client, make_user):
    token = access_token(db_client, make_user("beta", role="reception"))

    body = _create(db_client, token, slug="beta", phone="0981 123456").json()

    assert body["phone"] == "+595981123456"


def test_foreign_number_with_country_code_is_accepted(db_client, reception):
    _, token = reception

    assert _create(db_client, token, phone="+595 981 123456").json()["phone"] == "+595981123456"


@pytest.mark.parametrize(
    ("overrides", "field", "code"),
    [
        ({"phone": "123"}, "phone", "invalid_phone"),
        ({"phone": "telefone"}, "phone", "invalid_phone"),
        ({"email": "sem-arroba"}, "email", "invalid_email"),
        ({"consents": ["reminders"]}, "consents", "consent_required"),
        ({"consents": []}, "consents", "consent_required"),
        ({"name": "   "}, "name", "string_too_short"),
    ],
)
def test_invalid_customer(db_client, reception, overrides, field, code):
    _, token = reception

    response = _create(db_client, token, **overrides)

    assert response.status_code == 422
    assert response.json()["error"]["fields"][0] == {"field": field, "code": code}


def test_consent_can_be_withdrawn_and_given_again(db_client, reception):
    _, token = reception
    customer = _create(db_client, token, consents=["service", "marketing"]).json()
    url = f"/t/alpha/customers/{customer['id']}/consents"

    withdrawn = db_client.post(url, json={"purpose": "marketing", "granted": False},
                               headers=bearer(token)).json()  # fmt: skip
    again = db_client.post(url, json={"purpose": "marketing", "granted": True},
                           headers=bearer(token)).json()  # fmt: skip

    assert {c["purpose"] for c in withdrawn["consents"]} == {"service"}
    assert {c["purpose"] for c in again["consents"]} == {"service", "marketing"}


def test_consent_history_is_kept(db_settings, db_client, reception):
    _, token = reception
    customer = _create(db_client, token, consents=["service", "marketing"]).json()
    url = f"/t/alpha/customers/{customer['id']}/consents"
    db_client.post(url, json={"purpose": "marketing", "granted": False}, headers=bearer(token))
    db_client.post(url, json={"purpose": "marketing", "granted": True}, headers=bearer(token))

    databases = Databases(db_settings)
    with tenant_session(databases, load_tenant(databases, "alpha")) as session:
        rows = session.execute(
            text("SELECT revoked_at IS NOT NULL FROM consents WHERE customer_id = :id "
                 "AND purpose = 'marketing' ORDER BY granted_at"),
            {"id": customer["id"]},
        ).scalars().all()  # fmt: skip
    assert rows == [True, False]  # a retirada continua no histórico


def test_update_changes_only_sent_fields(db_client, reception):
    _, token = reception
    customer = _create(db_client, token).json()

    response = db_client.patch(
        f"/t/alpha/customers/{customer['id']}",
        json={"phone": "11 97777-6666", "email": None},
        headers=bearer(token),
    )

    body = response.json()
    assert body["phone"] == "+5511977776666"
    assert body["email"] is None
    assert body["name"] == "Maria Silva"


def test_list_is_paginated_and_alphabetical(db_client, make_user):
    token = access_token(db_client, make_user("gamma", role="reception"))
    for name in ("Zélia", "Ana", "Bruna"):
        _create(db_client, token, slug="gamma", name=name)

    page = db_client.get("/t/gamma/customers", params={"limit": 2}, headers=bearer(token)).json()

    assert page["total"] >= 3
    assert len(page["items"]) == 2
    names = [i["name"] for i in page["items"]]
    assert names == sorted(names)


def test_customer_of_another_salon_is_not_found(db_client, reception, make_user):
    _, token = reception
    customer = _create(db_client, token).json()
    beta_token = access_token(db_client, make_user("beta", role="owner"))

    url = f"/t/beta/customers/{customer['id']}"
    assert db_client.get(url, headers=bearer(beta_token)).status_code == 404
    assert db_client.patch(url, json={"name": "X"}, headers=bearer(beta_token)).status_code == 404


# --- auditoria ---------------------------------------------------------------------------


def test_owner_sees_who_created_viewed_and_changed(db_client, reception, owner_token):
    user, token = reception
    customer = _create(db_client, token).json()
    db_client.get(f"/t/alpha/customers/{customer['id']}", headers=bearer(token))
    db_client.patch(
        f"/t/alpha/customers/{customer['id']}",
        json={"name": "Maria S.", "email": "maria@exemplo.com"},  # e-mail igual: não mudou
        headers=bearer(token),
    )

    entries = _audit(db_client, owner_token, customer["id"])

    actions = [(e["action"], e["fields"]) for e in reversed(entries)]
    assert actions == [
        ("customer.created", ["email", "name", "phone"]),
        ("consent.granted", ["reminders", "service"]),
        ("customer.viewed", []),
        ("customer.updated", ["name"]),
    ]
    assert {e["actor"]["name"] for e in entries} == {"Pessoa reception"}
    assert {e["actor"]["id"] for e in entries} == {str(user.id)}
    assert all(e["occurred_at"] for e in entries)


def test_audit_never_stores_personal_values(db_settings, db_client, reception):
    _, token = reception
    customer = _create(db_client, token, name="Valor Secreto", email="secreto@x.com").json()

    databases = Databases(db_settings)
    with tenant_session(databases, load_tenant(databases, "alpha")) as session:
        dump = session.execute(
            text("SELECT string_agg(a::text, ' ') FROM audit_log a WHERE entity_id = :id"),
            {"id": customer["id"]},
        ).scalar()
    assert "Valor Secreto" not in dump
    assert "secreto@x.com" not in dump
    assert "98888" not in dump


def test_audit_is_paginated_with_before(db_client, reception, owner_token):
    _, token = reception
    customer = _create(db_client, token).json()
    for _ in range(3):
        db_client.get(f"/t/alpha/customers/{customer['id']}", headers=bearer(token))

    first = db_client.get(
        "/t/alpha/audit", params={"entity_id": customer["id"], "limit": 2},
        headers=bearer(owner_token),
    ).json()  # fmt: skip
    rest = db_client.get(
        "/t/alpha/audit",
        params={"entity_id": customer["id"], "before": first[-1]["occurred_at"]},
        headers=bearer(owner_token),
    ).json()

    assert len(first) == 2
    assert {e["id"] for e in first}.isdisjoint({e["id"] for e in rest})
    assert len(first) + len(rest) == 5  # criado + consentimento + 3 consultas


def test_failed_change_leaves_no_audit_entry(db_client, reception, owner_token):
    _, token = reception
    customer = _create(db_client, token).json()

    db_client.patch(
        f"/t/alpha/customers/{customer['id']}", json={"phone": "123"}, headers=bearer(token)
    )

    actions = [e["action"] for e in _audit(db_client, owner_token, customer["id"])]
    assert "customer.updated" not in actions


@pytest.mark.parametrize(
    "statement",
    ["UPDATE audit_log SET action = 'x'", "DELETE FROM audit_log", "TRUNCATE audit_log"],
)
def test_salon_cannot_rewrite_or_erase_the_audit_log(db_settings, statement, reception, db_client):
    _create(db_client, reception[1])
    databases = Databases(db_settings)

    with pytest.raises(ProgrammingError) as exc_info:
        with tenant_session(databases, load_tenant(databases, "alpha")) as session:
            session.execute(text(statement))

    assert exc_info.value.orig.sqlstate == "42501"


@pytest.mark.parametrize("statement", ["UPDATE t_alpha.audit_log SET action = 'x'",
                                       "DELETE FROM t_alpha.audit_log"])  # fmt: skip
def test_even_the_admin_cannot_rewrite_the_audit_log(db_settings, statement, reception, db_client):
    _create(db_client, reception[1])
    admin = create_engine(db_settings.database_admin_url, poolclass=NullPool)

    with pytest.raises(DBAPIError, match="somente INSERT"):
        with admin.begin() as conn:
            conn.execute(text(statement))


def test_audit_stays_append_only_after_new_migrations(db_settings, tenants):
    """Cada `migrate` reaplica os GRANTs; o log precisa continuar só de inserção."""
    migrate_tenants(db_settings, ["alpha"])
    admin = create_engine(db_settings.database_admin_url, poolclass=NullPool)

    with admin.connect() as conn:
        privileges = set(conn.execute(text(
            "SELECT privilege_type FROM information_schema.role_table_grants "
            "WHERE table_schema = 't_alpha' AND table_name = 'audit_log' AND grantee = :role"
        ), {"role": tenants["alpha"].tenant.role}).scalars())  # fmt: skip
    assert privileges == {"SELECT", "INSERT"}


def test_customer_data_never_goes_to_the_application_log(db_client, reception, capsys):
    _, token = reception
    customer = _create(db_client, token, name="Nome Sigiloso", email="sigilo@x.com").json()
    db_client.patch(f"/t/alpha/customers/{customer['id']}", json={"phone": "11 96666-5555"},
                    headers=bearer(token))  # fmt: skip

    output = capsys.readouterr().out
    for secret in ("Nome Sigiloso", "sigilo@x.com", "96666", "98888"):
        assert secret not in output


def test_unknown_customer(db_client, reception):
    _, token = reception

    response = db_client.get(f"/t/alpha/customers/{uuid.uuid4()}", headers=bearer(token))

    assert response.status_code == 404
