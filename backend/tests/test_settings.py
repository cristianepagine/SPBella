"""SAL-03: configurações do estabelecimento e idioma de cada pessoa."""

import re

import pytest
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

from app.core.infra.db import Databases
from app.core.infra.tenancy import update_tenant_profile
from app.core.tenants.provisioning import create_tenant
from app.registry import VERTICAL
from tests.test_auth import access_token, bearer

SLUG = "config-teste"


@pytest.fixture(scope="module")
def config_tenant(db_settings, tenants):
    """Salão só destes testes: aqui os dados mudam de propósito."""
    return create_tenant(
        db_settings, slug=SLUG, name="Salão Config", country="BR",
        owner_email="dono@config.test", owner_name="Dono", vertical=VERTICAL,
    ).tenant  # fmt: skip


@pytest.fixture
def owner_token(db_client, make_user, config_tenant):
    return access_token(db_client, make_user(SLUG, role="owner"))


def _patch(client, token, **changes):
    return client.patch(f"/t/{SLUG}/settings", json=changes, headers=bearer(token))


# --- configurações -----------------------------------------------------------------------


def test_owner_sees_the_settings(db_client, owner_token):
    body = db_client.get(f"/t/{SLUG}/settings", headers=bearer(owner_token)).json()

    assert body["currency"] == "BRL"
    assert body["country"] == "BR"
    assert "America/Sao_Paulo" in body["timezone_options"]
    assert "America/Manaus" in body["timezone_options"]


def test_paraguayan_salon_gets_paraguayan_timezone(db_client, make_user):
    token = access_token(db_client, make_user("beta", role="owner"))

    body = db_client.get("/t/beta/settings", headers=bearer(token)).json()

    assert body["timezone_options"] == ["America/Asuncion"]
    assert body["currency"] == "PYG"


def test_changes_apply_immediately_everywhere(db_client, owner_token):
    response = _patch(
        db_client, owner_token, name="  Salão Novo Nome ", locale="es", timezone="America/Manaus"
    )

    assert response.status_code == 200
    public = db_client.get(f"/t/{SLUG}").json()
    assert public["name"] == "Salão Novo Nome"
    assert public["locale"] == "es"
    assert public["timezone"] == "America/Manaus"
    _patch(
        db_client, owner_token, name="Salão Config", locale="pt-BR", timezone="America/Sao_Paulo"
    )


def test_only_sent_fields_change(db_client, owner_token):
    before = db_client.get(f"/t/{SLUG}").json()

    _patch(db_client, owner_token, timezone="America/Recife")

    after = db_client.get(f"/t/{SLUG}").json()
    assert after == {**before, "timezone": "America/Recife"}
    _patch(db_client, owner_token, timezone="America/Sao_Paulo")


@pytest.mark.parametrize(
    ("changes", "field", "code"),
    [
        ({"timezone": "America/Atlantida"}, "timezone", "invalid_timezone"),
        ({"name": "   "}, "name", "string_too_short"),
        ({"name": ""}, "name", "string_too_short"),
        ({"locale": "en"}, "locale", "literal_error"),
    ],
)
def test_invalid_settings(db_client, owner_token, changes, field, code):
    response = _patch(db_client, owner_token, **changes)

    assert response.status_code == 422
    assert response.json()["error"]["fields"][0] == {"field": field, "code": code}


def test_currency_and_other_fields_cannot_be_changed(db_client, owner_token):
    _patch(db_client, owner_token, currency="PYG", slug="outro", plan="whatsapp_api")

    public = db_client.get(f"/t/{SLUG}").json()
    assert public["currency"] == "BRL"
    assert public["slug"] == SLUG


def test_changing_one_salon_does_not_touch_another(db_client, owner_token):
    alpha_before = db_client.get("/t/alpha").json()

    _patch(db_client, owner_token, name="Só o meu muda")

    assert db_client.get("/t/alpha").json() == alpha_before
    _patch(db_client, owner_token, name="Salão Config")


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE public.tenants SET plan = 'whatsapp_api'",
        "UPDATE public.tenants SET currency = 'PYG'",
        "UPDATE public.tenants SET slug = 'x'",
        "UPDATE public.tenants SET status = 'active'",
        "UPDATE public.tenants SET schema_name = 't_x'",
        "DELETE FROM public.tenants",
        "INSERT INTO public.tenants (slug) VALUES ('x')",
    ],
)
def test_app_role_can_only_edit_name_locale_and_timezone(db_settings, config_tenant, statement):
    """Garantia do próprio banco: mesmo com um bug, a API não muda o resto da tabela."""
    with pytest.raises(ProgrammingError) as exc_info:
        with Databases(db_settings).control.begin() as conn:
            conn.execute(text(statement))

    assert exc_info.value.orig.sqlstate == "42501"


def test_profile_update_refuses_other_fields(db_settings, config_tenant):
    with pytest.raises(ValueError, match="não editáveis"):
        update_tenant_profile(Databases(db_settings), config_tenant.id, {"plan": "x"})


# --- idioma de cada pessoa ---------------------------------------------------------------


def test_each_person_chooses_their_own_language(db_client, make_user):
    user = make_user("alpha", role="professional")
    token = access_token(db_client, user)

    changed = db_client.patch("/t/alpha/auth/me", json={"locale": "es"}, headers=bearer(token))
    again = db_client.post(
        "/t/alpha/auth/login",
        json={"email": user.email, "password": user.password, "turnstile_token": "t"},
    )
    reset = db_client.patch("/t/alpha/auth/me", json={"locale": None}, headers=bearer(token))

    assert changed.json()["locale"] == "es"
    assert again.json()["user"]["locale"] == "es"  # vale em qualquer aparelho
    assert reset.json()["locale"] is None


def test_unknown_language_is_refused(db_client, make_user):
    token = access_token(db_client, make_user("alpha"))

    response = db_client.patch("/t/alpha/auth/me", json={"locale": "en"}, headers=bearer(token))

    assert response.status_code == 422


def test_password_email_goes_in_the_persons_language(db_client, make_user):
    user = make_user("alpha")  # salão brasileiro...
    token = access_token(db_client, user)
    db_client.patch("/t/alpha/auth/me", json={"locale": "es"}, headers=bearer(token))

    db_client.post(
        "/t/alpha/auth/forgot-password", json={"email": user.email, "turnstile_token": "t"}
    )

    email = db_client.app.state.mailer.outbox[-1]
    assert email.subject.startswith("Restablecer tu contraseña")  # ...pessoa em espanhol
    assert re.search(r"/alpha/reset-password#token=", email.body)
