"""Login, sessão, senha e permissões (com Postgres)."""

import json
import re
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

COOKIE = "spbella_refresh"


# --- utilitários -------------------------------------------------------------------------


def login(client, user, *, password=None, slug=None, turnstile="ok"):
    return client.post(
        f"/t/{slug or user.slug}/auth/login",
        json={
            "email": user.email,
            "password": password or user.password,
            "turnstile_token": turnstile,
        },
    )


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def access_token(client, user) -> str:
    response = login(client, user)
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def refresh_with(client, slug: str, token: str | None):
    """Chama /refresh enviando exatamente este cookie (ignora o que está guardado)."""
    client.cookies.clear()
    headers = {"Cookie": f"{COOKIE}={token}"} if token else {}
    return client.post(f"/t/{slug}/auth/refresh", headers=headers)


def set_cookie_header(response) -> str:
    return "; ".join(v for k, v in response.headers.multi_items() if k.lower() == "set-cookie")


def admin_sql(db_settings, sql: str, **params) -> None:
    engine = create_engine(db_settings.database_admin_url, poolclass=NullPool)
    with engine.begin() as conn:
        conn.execute(text(sql), params)


# --- login -------------------------------------------------------------------------------


def test_login_returns_token_and_httponly_cookie_scoped_to_the_salon(db_client, make_user):
    user = make_user("alpha", role="reception")

    response = login(db_client, user)

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 15 * 60
    assert body["user"] == {
        "id": str(user.id),
        "name": "Pessoa reception",
        "email": user.email,
        "role": "reception",
        "must_change_password": False,
        "permissions": [
            "agenda.manage",
            "agenda.view_all",
            "agenda.view_own",
            "customers.manage",
        ],
    }
    cookie = set_cookie_header(response)
    assert f"{COOKIE}=" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=strict" in cookie
    assert "Path=/t/alpha/auth" in cookie


def test_me_with_token(db_client, make_user):
    user = make_user("alpha")
    token = access_token(db_client, user)

    response = db_client.get("/t/alpha/auth/me", headers=bearer(token))

    assert response.status_code == 200
    assert response.json()["email"] == user.email


def test_email_is_case_insensitive(db_client, make_user):
    user = make_user("alpha")

    response = db_client.post(
        "/t/alpha/auth/login",
        json={
            "email": f"  {user.email.upper()} ",
            "password": user.password,
            "turnstile_token": "t",
        },
    )

    assert response.status_code == 200


def test_wrong_password_unknown_email_and_inactive_account_look_the_same(db_client, make_user):
    active = make_user("alpha")
    inactive = make_user("alpha", is_active=False)

    wrong_password = login(db_client, active, password="senha-errada-999")
    unknown = db_client.post(
        "/t/alpha/auth/login",
        json={"email": "ninguem@alpha.test", "password": "x" * 10, "turnstile_token": "t"},
    )
    disabled = login(db_client, inactive)

    for response in (wrong_password, unknown, disabled):
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "invalid_credentials"
        assert COOKIE not in set_cookie_header(response)


def test_login_requires_turnstile(db_client, make_user):
    user = make_user("alpha")
    db_client.app.state.turnstile.result = False

    response = login(db_client, user, turnstile="token-do-widget")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "turnstile_failed"
    assert db_client.app.state.turnstile.calls[-1] == ("token-do-widget", "testclient")


def test_login_is_rate_limited_per_account(db_client, make_user):
    user = make_user("alpha")
    for _ in range(10):
        assert login(db_client, user, password="senha-errada-999").status_code == 401

    blocked = login(db_client, user)  # nem a senha certa passa durante o bloqueio

    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "too_many_requests"
    assert int(blocked.headers["Retry-After"]) > 0


def test_login_does_not_log_email_or_password(db_client, make_user, capsys):
    user = make_user("alpha")
    login(db_client, user)
    login(db_client, user, password="senha-errada-999")

    output = capsys.readouterr().out
    assert "login_succeeded" in output
    assert "login_failed" in output
    assert user.email not in output
    assert user.password not in output


def test_access_log_identifies_salon_and_user(db_client, make_user, tenants, capsys):
    user = make_user("alpha")
    token = access_token(db_client, user)
    capsys.readouterr()

    db_client.get("/t/alpha/auth/me", headers=bearer(token))

    line = next(
        json.loads(raw)
        for raw in capsys.readouterr().out.splitlines()
        if '"event": "request"' in raw and "/auth/me" in raw
    )
    assert line["tenant_id"] == str(tenants["alpha"].tenant.id)
    assert line["user_id"] == str(user.id)


def test_login_from_another_origin_is_refused(db_client, make_user):
    user = make_user("alpha")

    response = db_client.post(
        "/t/alpha/auth/login",
        json={"email": user.email, "password": user.password, "turnstile_token": "t"},
        headers={"Origin": "https://site-malicioso.example"},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden_origin"


# --- token -------------------------------------------------------------------------------


def test_token_of_one_salon_is_refused_in_another(db_client, make_user):
    token = access_token(db_client, make_user("alpha"))

    response = db_client.get("/t/beta/auth/me", headers=bearer(token))

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


def test_credentials_of_one_salon_do_not_work_in_another(db_client, make_user):
    user = make_user("alpha")

    assert login(db_client, user, slug="beta").status_code == 401


def test_missing_token_is_401_with_www_authenticate(db_client):
    response = db_client.get("/t/alpha/auth/me")

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


def _forge(db_settings, user, tenants, **changes) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user.id),
        "tid": str(tenants["alpha"].tenant.id),
        "role": "owner",
        "typ": "access",
        "iat": now,
        "exp": now + timedelta(minutes=5),
    }
    secret = changes.pop("secret", db_settings.jwt_secret.get_secret_value())
    algorithm = changes.pop("algorithm", "HS256")
    payload.update(changes)
    return jwt.encode(payload, secret, algorithm=algorithm)


@pytest.mark.parametrize(
    "changes",
    [
        {"exp": datetime.now(UTC) - timedelta(seconds=1)},
        {"secret": "outro-segredo-qualquer-com-32-caracteres!"},
        {"typ": "refresh"},
        {"sub": "nao-e-uuid"},
        {"algorithm": "HS512"},
    ],
    ids=["vencido", "outro-segredo", "tipo-errado", "sub-invalido", "outro-algoritmo"],
)
def test_forged_or_expired_tokens_are_refused(db_client, db_settings, make_user, tenants, changes):
    token = _forge(db_settings, make_user("alpha"), tenants, **changes)

    assert db_client.get("/t/alpha/auth/me", headers=bearer(token)).status_code == 401


def test_unsigned_token_is_refused(db_client, make_user, tenants):
    user = make_user("alpha")
    token = jwt.encode(
        {"sub": str(user.id), "tid": str(tenants["alpha"].tenant.id), "typ": "access",
         "iat": 1, "exp": 4102444800},
        key=None,
        algorithm="none",
    )  # fmt: skip

    assert db_client.get("/t/alpha/auth/me", headers=bearer(token)).status_code == 401


def test_role_comes_from_the_database_not_from_the_token(
    db_client, db_settings, make_user, tenants
):
    professional = make_user("alpha", role="professional")
    token = _forge(db_settings, professional, tenants, role="owner")  # token diz "owner"

    response = db_client.get("/t/alpha/_probe/owner-only", headers=bearer(token))

    assert response.status_code == 403


def test_deactivated_user_loses_access_immediately(db_client, db_settings, make_user):
    user = make_user("alpha")
    token = access_token(db_client, user)

    admin_sql(db_settings, "UPDATE t_alpha.users SET is_active = false WHERE id = :id", id=user.id)

    assert db_client.get("/t/alpha/auth/me", headers=bearer(token)).status_code == 401
    assert db_client.post("/t/alpha/auth/refresh").status_code == 401


# --- perfis ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("role", "owner_only", "staff_only"),
    [
        ("owner", 200, 200),
        ("reception", 403, 200),
        ("professional", 403, 403),
    ],
)
def test_permissions_by_role(db_client, make_user, role, owner_only, staff_only):
    token = access_token(db_client, make_user("alpha", role=role))

    assert db_client.get("/t/alpha/_probe/owner-only", headers=bearer(token)).status_code == (
        owner_only
    )
    assert db_client.get("/t/alpha/_probe/staff-only", headers=bearer(token)).status_code == (
        staff_only
    )
    forbidden = db_client.get("/t/alpha/_probe/owner-only", headers=bearer(token))
    if owner_only == 403:
        assert forbidden.json()["error"]["code"] == "forbidden"


def test_protected_route_without_token_is_401(db_client):
    assert db_client.get("/t/alpha/_probe/any-user").status_code == 401


# --- senha provisória e troca de senha ---------------------------------------------------


def test_temporary_password_must_be_changed_first(db_client, make_user):
    user = make_user("alpha", must_change_password=True)
    session = login(db_client, user).json()
    token = session["access_token"]
    assert session["user"]["must_change_password"] is True

    blocked = db_client.get("/t/alpha/_probe/any-user", headers=bearer(token))
    me = db_client.get("/t/alpha/auth/me", headers=bearer(token))
    changed = db_client.post(
        "/t/alpha/auth/change-password",
        json={"current_password": user.password, "new_password": "nova-senha-forte-1"},
        headers=bearer(token),
    )
    new_token = changed.json()["access_token"]

    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "password_change_required"
    assert me.status_code == 200
    assert changed.status_code == 200
    assert changed.json()["user"]["must_change_password"] is False
    assert db_client.get("/t/alpha/_probe/any-user", headers=bearer(new_token)).status_code == 200


def test_change_password_with_wrong_current_password(db_client, make_user):
    user = make_user("alpha")
    token = access_token(db_client, user)

    response = db_client.post(
        "/t/alpha/auth/change-password",
        json={"current_password": "errada-123", "new_password": "nova-senha-forte-1"},
        headers=bearer(token),
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "wrong_current_password"


@pytest.mark.parametrize(
    ("new_password", "reason"),
    [
        ("curta", "too_short"),
        ("a" * 129, "too_long"),
        ("aaaabbbb", "too_simple"),
        ("senha-forte-123", "same_as_current"),
    ],
)
def test_change_password_rejects_weak_passwords(db_client, make_user, new_password, reason):
    user = make_user("alpha")
    token = access_token(db_client, user)

    response = db_client.post(
        "/t/alpha/auth/change-password",
        json={"current_password": user.password, "new_password": new_password},
        headers=bearer(token),
    )

    if reason == "too_long":  # barrado já na validação do corpo (max_length)
        assert response.status_code == 422
        return
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "weak_password"
    assert response.json()["error"]["fields"] == [{"field": "new_password", "code": reason}]


def test_password_containing_the_email_is_rejected(db_client, make_user):
    user = make_user("alpha")
    token = access_token(db_client, user)
    local = user.email.split("@")[0]

    response = db_client.post(
        "/t/alpha/auth/change-password",
        json={"current_password": user.password, "new_password": f"{local}!2026"},
        headers=bearer(token),
    )

    assert response.json()["error"]["fields"][0]["code"] == "contains_email"


def test_change_password_ends_other_sessions(db_client, make_user):
    user = make_user("alpha")
    login(db_client, user)
    other_device = db_client.cookies.get(COOKIE)
    token = access_token(db_client, user)

    db_client.post(
        "/t/alpha/auth/change-password",
        json={"current_password": user.password, "new_password": "nova-senha-forte-1"},
        headers=bearer(token),
    )

    assert refresh_with(db_client, "alpha", other_device).status_code == 401
    assert login(db_client, user).status_code == 401
    assert login(db_client, user, password="nova-senha-forte-1").status_code == 200


# --- refresh e logout --------------------------------------------------------------------


def test_refresh_rotates_the_cookie(db_client, make_user):
    login(db_client, make_user("alpha"))
    first = db_client.cookies.get(COOKIE)

    response = refresh_with(db_client, "alpha", first)

    assert response.status_code == 200
    assert response.json()["access_token"]
    second = response.cookies.get(COOKIE)
    assert second and second != first
    assert refresh_with(db_client, "alpha", second).status_code == 200


def test_refresh_race_between_tabs_does_not_end_the_session(db_client, make_user):
    login(db_client, make_user("alpha"))
    first = db_client.cookies.get(COOKIE)
    second = refresh_with(db_client, "alpha", first).cookies.get(COOKIE)

    late_tab = refresh_with(db_client, "alpha", first)  # outra aba, com o cookie antigo

    assert late_tab.status_code == 401
    assert late_tab.json()["error"]["code"] == "refresh_superseded"
    assert COOKIE not in set_cookie_header(late_tab)  # não apaga o cookie novo
    assert refresh_with(db_client, "alpha", second).status_code == 200


def test_reusing_an_old_refresh_ends_the_whole_session(db_client, db_settings, make_user):
    db_client.app.state.settings = db_settings.model_copy(update={"refresh_reuse_grace_seconds": 0})
    login(db_client, make_user("alpha"))
    stolen = db_client.cookies.get(COOKIE)
    legit = refresh_with(db_client, "alpha", stolen).cookies.get(COOKIE)

    attacker = refresh_with(db_client, "alpha", stolen)

    assert attacker.status_code == 401
    assert attacker.json()["error"]["code"] == "refresh_invalid"
    assert refresh_with(db_client, "alpha", legit).status_code == 401  # a família toda caiu


def test_refresh_without_cookie(db_client):
    response = refresh_with(db_client, "alpha", None)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "refresh_invalid"


def test_refresh_cookie_of_one_salon_is_useless_in_another(db_client, make_user):
    login(db_client, make_user("alpha"))
    cookie = db_client.cookies.get(COOKIE)

    assert refresh_with(db_client, "beta", cookie).status_code == 401


def test_expired_refresh_is_refused(db_client, db_settings, make_user):
    user = make_user("alpha")
    login(db_client, user)
    cookie = db_client.cookies.get(COOKIE)
    admin_sql(
        db_settings,
        "UPDATE t_alpha.refresh_tokens SET expires_at = now() - interval '1 minute'"
        " WHERE user_id = :id",
        id=user.id,
    )

    assert refresh_with(db_client, "alpha", cookie).status_code == 401


def test_refresh_from_another_origin_is_refused(db_client, make_user):
    login(db_client, make_user("alpha"))

    response = db_client.post(
        "/t/alpha/auth/refresh", headers={"Origin": "https://site-malicioso.example"}
    )

    assert response.status_code == 403


def test_logout_ends_the_session_and_clears_the_cookie(db_client, make_user):
    login(db_client, make_user("alpha"))
    cookie = db_client.cookies.get(COOKIE)

    response = db_client.post("/t/alpha/auth/logout")

    assert response.status_code == 204
    assert f'{COOKIE}=""' in set_cookie_header(response) or "Max-Age=0" in set_cookie_header(
        response
    )
    assert refresh_with(db_client, "alpha", cookie).status_code == 401


def test_logout_without_session_is_fine(db_client):
    assert db_client.post("/t/alpha/auth/logout").status_code == 204


# --- esqueci a senha ---------------------------------------------------------------------


def _outbox(client):
    return client.app.state.mailer.outbox


def _reset_token(email) -> str:
    match = re.search(r"/reset-password#token=([\w-]+)", email.body)
    assert match, email.body
    return match.group(1)


def test_forgot_password_sends_link_in_the_salon_language(db_client, make_user):
    br, py = make_user("alpha"), make_user("beta")
    outbox = _outbox(db_client)

    for user in (br, py):
        response = db_client.post(
            f"/t/{user.slug}/auth/forgot-password",
            json={"email": user.email, "turnstile_token": "t"},
        )
        assert response.status_code == 202

    pt, es = outbox[-2], outbox[-1]
    assert pt.to == br.email
    assert pt.subject == "Redefinir sua senha – Salão Alpha"
    assert "http://localhost:5173/alpha/reset-password#token=" in pt.body
    assert es.subject == "Restablecer tu contraseña – Salão Beta"
    assert "/beta/reset-password#token=" in es.body


def test_forgot_password_for_unknown_email_looks_the_same(db_client):
    before = len(_outbox(db_client))

    response = db_client.post(
        "/t/alpha/auth/forgot-password",
        json={"email": "ninguem@alpha.test", "turnstile_token": "t"},
    )

    assert response.status_code == 202
    assert len(_outbox(db_client)) == before


def test_forgot_password_is_rate_limited(db_client):
    responses = [
        db_client.post(
            "/t/alpha/auth/forgot-password",
            json={"email": f"x{i}@alpha.test", "turnstile_token": "t"},
        )
        for i in range(6)
    ]

    assert [r.status_code for r in responses] == [202] * 5 + [429]


def _request_reset(client, user) -> str:
    client.post(
        f"/t/{user.slug}/auth/forgot-password", json={"email": user.email, "turnstile_token": "t"}
    )
    return _reset_token(_outbox(client)[-1])


def _reset(client, slug, token, password="senha-nova-forte-9"):
    return client.post(
        f"/t/{slug}/auth/reset-password",
        json={"token": token, "new_password": password, "turnstile_token": "t"},
    )


def test_reset_password_flow(db_client, make_user):
    user = make_user("alpha", must_change_password=True)
    login(db_client, user)
    old_session = db_client.cookies.get(COOKIE)
    token = _request_reset(db_client, user)

    response = _reset(db_client, "alpha", token)

    assert response.status_code == 204
    assert login(db_client, user).status_code == 401
    new_login = login(db_client, user, password="senha-nova-forte-9")
    assert new_login.status_code == 200
    assert new_login.json()["user"]["must_change_password"] is False
    assert refresh_with(db_client, "alpha", old_session).status_code == 401


def test_reset_link_works_only_once(db_client, make_user):
    token = _request_reset(db_client, make_user("alpha"))

    assert _reset(db_client, "alpha", token).status_code == 204
    second = _reset(db_client, "alpha", token, password="outra-senha-forte-8")

    assert second.status_code == 400
    assert second.json()["error"]["code"] == "invalid_reset_token"


def test_reset_link_expires(db_client, db_settings, make_user):
    user = make_user("alpha")
    token = _request_reset(db_client, user)
    admin_sql(
        db_settings,
        "UPDATE t_alpha.password_reset_tokens SET expires_at = now() - interval '1 minute'"
        " WHERE user_id = :id",
        id=user.id,
    )

    assert _reset(db_client, "alpha", token).status_code == 400


def test_reset_link_of_one_salon_is_useless_in_another(db_client, make_user):
    token = _request_reset(db_client, make_user("alpha"))

    assert _reset(db_client, "beta", token).status_code == 400
    assert _reset(db_client, "alpha", token).status_code == 204


def test_weak_password_on_reset_keeps_the_link_valid(db_client, make_user):
    token = _request_reset(db_client, make_user("alpha"))

    weak = _reset(db_client, "alpha", token, password="curta")

    assert weak.status_code == 422
    assert _reset(db_client, "alpha", token).status_code == 204


def test_reset_requires_turnstile(db_client, make_user):
    token = _request_reset(db_client, make_user("alpha"))
    db_client.app.state.turnstile.result = False

    assert _reset(db_client, "alpha", token).json()["error"]["code"] == "turnstile_failed"
