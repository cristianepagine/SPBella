"""SAL-02: o dono cadastra e administra a equipe."""

import pytest

from app.core.accounts import permissions
from app.core.accounts.permissions import Permission
from tests.test_auth import COOKIE, access_token, bearer, login, refresh_with


@pytest.fixture
def owner(make_user):
    return make_user("alpha", role="owner")


def _add(client, token, *, role="reception", email=None, name="Carla Souza"):
    import uuid

    return client.post(
        "/t/alpha/team",
        json={"name": name, "email": email or f"carla-{uuid.uuid4().hex[:6]}@alpha.test",
              "role": role},
        headers=bearer(token),
    )  # fmt: skip


def test_owner_lists_the_team(db_client, owner):
    token = access_token(db_client, owner)

    response = db_client.get("/t/alpha/team", headers=bearer(token))

    assert response.status_code == 200
    me = next(m for m in response.json() if m["id"] == str(owner.id))
    assert me["role"] == "owner"
    assert me["is_active"] is True
    assert "password_hash" not in me


def test_new_member_gets_a_temporary_password_and_must_change_it(db_client, owner):
    token = access_token(db_client, owner)

    created = _add(db_client, token, email="  Nova.Pessoa@Alpha.Test ")

    assert created.status_code == 201
    body = created.json()
    assert body["member"]["email"] == "nova.pessoa@alpha.test"
    assert body["member"]["must_change_password"] is True
    session = db_client.post(
        "/t/alpha/auth/login",
        json={"email": "nova.pessoa@alpha.test", "password": body["temporary_password"],
              "turnstile_token": "t"},
    ).json()  # fmt: skip
    assert session["user"]["role"] == "reception"
    assert session["user"]["must_change_password"] is True


def test_duplicate_email_is_refused(db_client, owner):
    token = access_token(db_client, owner)

    response = _add(db_client, token, email=owner.email.upper())

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "email_taken"


@pytest.mark.parametrize(
    ("payload", "field"),
    [
        ({"name": "X", "email": "sem-arroba", "role": "reception"}, "email"),
        ({"name": "X", "email": "x@alpha.test", "role": "gerente"}, "role"),
        ({"name": "", "email": "x@alpha.test", "role": "reception"}, "name"),
    ],
)
def test_invalid_member_data(db_client, owner, payload, field):
    token = access_token(db_client, owner)

    response = db_client.post("/t/alpha/team", json=payload, headers=bearer(token))

    assert response.status_code == 422
    assert response.json()["error"]["fields"][0]["field"] == field


def test_role_change_takes_effect_immediately(db_client, owner, make_user):
    member = make_user("alpha", role="reception")
    member_token = access_token(db_client, member)
    owner_token = access_token(db_client, owner)

    response = db_client.patch(
        f"/t/alpha/team/{member.id}", json={"role": "professional"}, headers=bearer(owner_token)
    )

    assert response.status_code == 200
    me = db_client.get("/t/alpha/auth/me", headers=bearer(member_token)).json()
    assert me["role"] == "professional"  # mesmo token antigo: o perfil vem do banco
    assert me["permissions"] == ["agenda.view_own"]


def test_deactivating_someone_ends_their_sessions(db_client, owner, make_user):
    member = make_user("alpha", role="reception")
    login(db_client, member)
    member_cookie = db_client.cookies.get(COOKIE)
    member_token = access_token(db_client, member)
    owner_token = access_token(db_client, owner)

    response = db_client.patch(
        f"/t/alpha/team/{member.id}", json={"is_active": False}, headers=bearer(owner_token)
    )

    assert response.json()["is_active"] is False
    assert db_client.get("/t/alpha/auth/me", headers=bearer(member_token)).status_code == 401
    assert refresh_with(db_client, "alpha", member_cookie).status_code == 401
    assert login(db_client, member).status_code == 401


def test_nobody_changes_their_own_access(db_client, owner):
    token = access_token(db_client, owner)
    url = f"/t/alpha/team/{owner.id}"

    demote = db_client.patch(url, json={"role": "reception"}, headers=bearer(token))
    disable = db_client.patch(url, json={"is_active": False}, headers=bearer(token))
    rename = db_client.patch(url, json={"name": "Novo Nome"}, headers=bearer(token))

    assert demote.status_code == 409
    assert demote.json()["error"]["code"] == "cannot_change_self"
    assert disable.status_code == 409
    assert rename.status_code == 200


def test_there_is_always_an_active_owner(db_client, make_user, monkeypatch):
    # Hoje só donos gerenciam a equipe, então o caso só aparece se a matriz mudar;
    # a trava existe para quando mudar.
    monkeypatch.setitem(
        permissions.ROLE_PERMISSIONS,
        "reception",
        permissions.ROLE_PERMISSIONS["reception"] | {Permission.TEAM_MANAGE},
    )
    manager = make_user("alpha", role="reception")
    token = access_token(db_client, manager)
    owners = [
        m for m in db_client.get("/t/alpha/team", headers=bearer(token)).json()
        if m["role"] == "owner" and m["is_active"]
    ]  # fmt: skip

    responses = [
        db_client.patch(
            f"/t/alpha/team/{m['id']}", json={"is_active": False}, headers=bearer(token)
        )
        for m in owners
    ]

    assert [r.status_code for r in responses][:-1] == [200] * (len(owners) - 1)
    assert responses[-1].status_code == 409
    assert responses[-1].json()["error"]["code"] == "last_owner"
    for m in owners[:-1]:  # devolve o estado para os outros testes
        db_client.patch(f"/t/alpha/team/{m['id']}", json={"is_active": True}, headers=bearer(token))


def test_reset_password_gives_a_new_temporary_password(db_client, owner, make_user):
    member = make_user("alpha", role="professional")
    login(db_client, member)
    old_cookie = db_client.cookies.get(COOKIE)
    owner_token = access_token(db_client, owner)

    response = db_client.post(
        f"/t/alpha/team/{member.id}/reset-password", headers=bearer(owner_token)
    )

    temporary = response.json()["temporary_password"]
    assert login(db_client, member).status_code == 401
    session = login(db_client, member, password=temporary).json()
    assert session["user"]["must_change_password"] is True
    assert refresh_with(db_client, "alpha", old_cookie).status_code == 401


def test_owner_of_one_salon_cannot_touch_another_salons_team(db_client, make_user):
    alpha_member = make_user("alpha", role="reception")
    beta_owner = make_user("beta", role="owner")
    token = access_token(db_client, beta_owner)

    response = db_client.patch(
        f"/t/beta/team/{alpha_member.id}", json={"is_active": False}, headers=bearer(token)
    )

    assert response.status_code == 404
    assert login(db_client, alpha_member).status_code == 200


def test_team_changes_are_logged_without_personal_data(db_client, owner, capsys):
    token = access_token(db_client, owner)
    created = _add(db_client, token, email="logada@alpha.test", name="Pessoa Logada").json()
    db_client.patch(
        f"/t/alpha/team/{created['member']['id']}", json={"name": "Outro Nome"},
        headers=bearer(token),
    )  # fmt: skip

    output = capsys.readouterr().out
    assert "team_member_added" in output
    assert "team_member_changed" in output
    for secret in (
        "logada@alpha.test",
        "Pessoa Logada",
        "Outro Nome",
        created["temporary_password"],
    ):
        assert secret not in output
