"""Fixtures dos testes.

Testes que precisam de Postgres usam `db_settings`/`tenants`. Eles exigem a variável
TEST_ADMIN_DATABASE_URL (um superusuário). Sem ela, são pulados; com REQUIRE_DB_TESTS=1 (CI),
falham, para que os testes de isolamento nunca deixem de rodar sem ninguém perceber.

Os testes criam e apagam os bancos spbella_test e spbella_test_dedicated e os papéis
spbella_test_*. Não use um servidor com dados reais.
"""

import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, make_url, text
from sqlalchemy.engine import URL
from sqlalchemy.pool import NullPool

from app.core.config import Settings
from app.main import create_app
from app.provisioning import CreatedTenant, create_tenant, init_database
from tests.probe import router as probe_router

ADMIN_URL = os.getenv("TEST_ADMIN_DATABASE_URL")
REQUIRE_DB = os.getenv("REQUIRE_DB_TESTS") == "1"

TEST_DB = "spbella_test"
DEDICATED_DB = "spbella_test_dedicated"
ROLE_PREFIX = "spbella_test_"
APP_ROLE = "spbella_test_app"
APP_PASSWORD = "app-test-password"


@pytest.fixture
def settings() -> Settings:
    return Settings(app_env="test", cors_origins=["http://localhost:5173"])


@pytest.fixture
def client(settings: Settings) -> TestClient:
    return TestClient(create_app(settings), raise_server_exceptions=False)


# --- Postgres ----------------------------------------------------------------------------


def _url(url: URL) -> str:
    return url.render_as_string(hide_password=False)


def _reset_server(server: URL) -> None:
    engine = create_engine(_url(server), poolclass=NullPool, isolation_level="AUTOCOMMIT")
    with engine.connect() as conn:
        for db in (TEST_DB, DEDICATED_DB):
            conn.execute(text(f'DROP DATABASE IF EXISTS "{db}" WITH (FORCE)'))
        roles = conn.execute(
            text("SELECT rolname FROM pg_roles WHERE rolname LIKE :p"), {"p": ROLE_PREFIX + "%"}
        ).scalars()
        for role in list(roles):
            conn.execute(text(f'DROP ROLE "{role}"'))


@pytest.fixture(scope="session")
def db_settings() -> Iterator[Settings]:
    if not ADMIN_URL:
        message = "defina TEST_ADMIN_DATABASE_URL para rodar os testes com Postgres"
        if REQUIRE_DB:
            pytest.fail(message)
        pytest.skip(message)

    server = make_url(ADMIN_URL)
    _reset_server(server)
    engine = create_engine(_url(server), poolclass=NullPool, isolation_level="AUTOCOMMIT")
    with engine.connect() as conn:
        for db in (TEST_DB, DEDICATED_DB):
            conn.execute(text(f'CREATE DATABASE "{db}"'))

    admin_main = server.set(database=TEST_DB)
    app_main = admin_main.set(username=APP_ROLE, password=APP_PASSWORD)
    os.environ["TENANT_DSN_DEDICATED"] = _url(app_main.set(database=DEDICATED_DB))
    os.environ["TENANT_DSN_DEDICATED_ADMIN"] = _url(admin_main.set(database=DEDICATED_DB))

    settings = Settings(
        app_env="test",
        database_url=_url(app_main),
        database_admin_url=_url(admin_main),
        tenant_role_prefix=ROLE_PREFIX,
        db_pool_size=2,
    )
    init_database(settings)
    yield settings
    _reset_server(server)


@pytest.fixture(scope="session")
def tenants(db_settings: Settings) -> dict[str, CreatedTenant]:
    """alpha (BR) e beta (PY) no banco principal; gamma em banco dedicado."""
    specs = {
        "alpha": {"country": "BR"},
        "beta": {"country": "PY"},
        "gamma": {"country": "BR", "dsn_ref": "TENANT_DSN_DEDICATED"},
    }
    return {
        slug: create_tenant(
            db_settings,
            slug=slug,
            name=f"Salão {slug.title()}",
            owner_email=f"dono@{slug}.test",
            owner_name=f"Dono {slug}",
            **spec,
        )
        for slug, spec in specs.items()
    }


@pytest.fixture(scope="session")
def db_client(db_settings: Settings, tenants: dict[str, CreatedTenant]) -> Iterator[TestClient]:
    """Cliente HTTP com as rotas de teste em /t/{slug}/_probe (ver tests/probe.py)."""
    app = create_app(db_settings)
    app.include_router(probe_router)
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client
