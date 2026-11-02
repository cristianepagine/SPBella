"""PROVA de que o salão A nunca lê nem grava dados do salão B.

Três camadas são testadas:
1. HTTP: as rotas só enxergam o salão do slug da URL.
2. Banco: o papel de um salão é barrado pelo Postgres ao tentar outro schema.
   Limite conhecido: o Postgres decide quem pode fazer SET ROLE pelo usuário da CONEXÃO (o papel
   da aplicação, membro de todos os salões). Então SQL injetado poderia trocar de papel. A defesa
   contra isso é não existir SQL montado com texto (lint S608) e só tenancy.py usar SET ROLE
   (tests/test_architecture.py). Ver docs/arquitetura.md.
3. Conexões: o pool não "vaza" papel nem search_path de um pedido para outro.
"""

import os
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.pool import NullPool

from app.core.db import Databases
from app.core.tenancy import load_tenant, tenant_session
from tests.conftest import APP_ROLE

INSUFFICIENT_PRIVILEGE = "42501"


def _email() -> str:
    return f"{uuid.uuid4().hex[:10]}@isolamento.test"


def _create(client, slug: str, name: str = "Pessoa") -> dict:
    response = client.post(f"/t/{slug}/_probe/users", json={"name": name, "email": _email()})
    assert response.status_code == 200, response.text
    return response.json()


def _ctx(db_settings, slug):
    databases = Databases(db_settings)
    tenant = load_tenant(databases, slug)
    assert tenant is not None
    return databases, tenant


def _assert_denied(exc_info) -> None:
    assert exc_info.value.orig.sqlstate == INSUFFICIENT_PRIVILEGE


# --- 1. HTTP -----------------------------------------------------------------------------


def test_record_created_in_a_does_not_appear_in_b(db_client):
    created = _create(db_client, "alpha")

    alpha_ids = {u["id"] for u in db_client.get("/t/alpha/_probe/users").json()}
    beta_ids = {u["id"] for u in db_client.get("/t/beta/_probe/users").json()}

    assert created["id"] in alpha_ids
    assert created["id"] not in beta_ids


@pytest.mark.parametrize("method", ["get", "patch", "delete"])
def test_b_cannot_read_change_or_delete_a_record_by_id(db_client, method):
    created = _create(db_client, "alpha", name="Original")
    url = f"/t/beta/_probe/users/{created['id']}"

    response = (
        db_client.patch(url, json={"name": "Invadido"})
        if method == "patch"
        else getattr(db_client, method)(url)
    )

    assert response.status_code == 404
    still_there = db_client.get(f"/t/alpha/_probe/users/{created['id']}")
    assert still_there.status_code == 200
    assert still_there.json()["name"] == "Original"


def test_same_email_can_exist_in_two_salons(db_client):
    email = _email()
    for slug in ("alpha", "beta"):
        response = db_client.post(f"/t/{slug}/_probe/users", json={"name": "X", "email": email})
        assert response.status_code == 200


def test_request_runs_with_the_salon_role_and_schema(db_client, tenants):
    for slug in ("alpha", "beta", "gamma"):
        body = db_client.get(f"/t/{slug}/_probe/whoami").json()
        assert body["user"] == tenants[slug].tenant.role
        assert body["search_path"] == f'"{tenants[slug].tenant.schema}"'


def test_error_in_route_rolls_back_everything(db_client):
    email = _email()

    response = db_client.post("/t/alpha/_probe/fail", json={"name": "Fantasma", "email": email})

    assert response.status_code == 409
    emails = {u["email"] for u in db_client.get("/t/alpha/_probe/users").json()}
    assert email not in emails


@pytest.mark.parametrize("slug", ["nao-existe", "ALPHA", "alpha;drop", "t_alpha", "ab", "admin"])
def test_unknown_or_malformed_slug_is_404(db_client, slug):
    response = db_client.get(f"/t/{slug}/_probe/users")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "tenant_not_found"


def test_suspended_salon_is_404(db_client, db_settings):
    from app.provisioning import create_tenant

    create_tenant(
        db_settings, slug="suspenso", name="Suspenso", country="BR",
        owner_email="dono@suspenso.test", owner_name="Dono",
    )  # fmt: skip
    admin = create_engine(db_settings.database_admin_url, poolclass=NullPool)
    with admin.begin() as conn:
        conn.execute(text("UPDATE public.tenants SET status = 'suspended' WHERE slug = 'suspenso'"))

    assert db_client.get("/t/suspenso").status_code == 404
    assert db_client.get("/t/suspenso/_probe/users").status_code == 404


def test_dedicated_salon_data_lives_in_its_own_database(db_client, db_settings):
    created = _create(db_client, "gamma")

    main = create_engine(db_settings.database_admin_url, poolclass=NullPool)
    dedicated = create_engine(os.environ["TENANT_DSN_DEDICATED_ADMIN"], poolclass=NullPool)
    with main.connect() as conn:
        assert conn.execute(text("SELECT to_regnamespace('t_gamma')")).scalar() is None
    with dedicated.connect() as conn:
        found = conn.execute(
            text("SELECT count(*) FROM t_gamma.users WHERE id = :id"), {"id": created["id"]}
        ).scalar()
    assert found == 1


# --- 2. Banco ----------------------------------------------------------------------------


def test_salon_role_is_denied_on_another_salon_schema(db_settings, tenants):
    databases, beta = _ctx(db_settings, "beta")

    with pytest.raises(ProgrammingError) as exc_info:
        with tenant_session(databases, beta) as session:
            session.execute(text("SELECT count(*) FROM t_alpha.users"))

    _assert_denied(exc_info)


def test_salon_role_cannot_write_into_another_salon(db_settings, tenants):
    databases, beta = _ctx(db_settings, "beta")

    with pytest.raises(ProgrammingError) as exc_info:
        with tenant_session(databases, beta) as session:
            session.execute(
                text(
                    "INSERT INTO t_alpha.users (name, email, password_hash, role)"
                    " VALUES ('x', 'x@x.test', 'x', 'owner')"
                )
            )

    _assert_denied(exc_info)


def test_salon_role_cannot_read_the_salon_list(db_settings, tenants):
    databases, alpha = _ctx(db_settings, "alpha")

    with pytest.raises(ProgrammingError) as exc_info:
        with tenant_session(databases, alpha) as session:
            session.execute(text("SELECT slug FROM public.tenants"))

    _assert_denied(exc_info)


@pytest.mark.parametrize(
    "statement",
    [
        "CREATE TABLE intrusa (id int)",
        "DROP TABLE users",
        "ALTER TABLE users ADD COLUMN x int",
        "UPDATE alembic_version SET version_num = 'x'",
    ],
)
def test_salon_role_cannot_change_structure(db_settings, tenants, statement):
    databases, alpha = _ctx(db_settings, "alpha")

    with pytest.raises(ProgrammingError) as exc_info:
        with tenant_session(databases, alpha) as session:
            session.execute(text(statement))

    _assert_denied(exc_info)


def test_app_role_alone_cannot_read_salon_tables(db_settings, tenants):
    """Sem SET ROLE, o papel da aplicação (NOINHERIT) não lê tabela de salão nenhuma."""
    databases = Databases(db_settings)

    with pytest.raises(ProgrammingError) as exc_info:
        with databases.control.connect() as conn:
            conn.execute(text("SELECT count(*) FROM t_alpha.users"))

    _assert_denied(exc_info)


# --- 3. Conexões -------------------------------------------------------------------------


def test_connection_returns_clean_to_the_pool(db_settings, tenants):
    databases = Databases(db_settings.model_copy(update={"db_pool_size": 1}))
    alpha = load_tenant(databases, "alpha")

    with tenant_session(databases, alpha) as session:
        pid_inside = session.execute(text("SELECT pg_backend_pid()")).scalar()
        assert session.execute(text("SELECT current_user")).scalar() == alpha.role

    with databases.control.connect() as conn:
        pid_after, user, path = conn.execute(
            text("SELECT pg_backend_pid(), current_user, current_setting('search_path')")
        ).one()

    assert pid_after == pid_inside  # mesma conexão física, reaproveitada
    assert user == APP_ROLE
    assert "t_alpha" not in path


def test_parallel_sessions_never_mix_salons(db_settings, tenants):
    databases = Databases(db_settings.model_copy(update={"db_pool_size": 2}))
    contexts = {slug: load_tenant(databases, slug) for slug in ("alpha", "beta")}

    def probe(i: int) -> tuple[str, str, str]:
        slug = "alpha" if i % 2 else "beta"
        tenant = contexts[slug]
        with tenant_session(databases, tenant) as session:
            session.execute(text("SELECT pg_sleep(0.005)"))
            user, path = session.execute(
                text("SELECT current_user, current_setting('search_path')")
            ).one()
        return tenant.role, user, path

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(probe, range(60)))

    for expected_role, user, path in results:
        assert user == expected_role
        assert path == f'"{expected_role.removeprefix("spbella_test_")}"'
