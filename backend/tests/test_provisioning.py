import time

import pytest
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

from app import cli
from app.core.accounts.models import User
from app.core.infra.config import Settings
from app.core.infra.db import Databases
from app.core.infra.migrations import alembic_config, tenant_head, tenant_version_dirs
from app.core.infra.security import verify_password
from app.core.infra.tenancy import load_tenant, tenant_session
from app.core.tenants import provisioning
from app.core.tenants.provisioning import (
    DEMO_PASSWORD,
    MIGRATION_LOCK_KEY,
    ProvisioningError,
    create_tenant,
    list_tenants,
    migrate_tenants,
    seed_demo,
)
from app.core.vertical import Vertical
from app.registry import VERTICAL
from tests.conftest import production_settings

# --- validações (sem banco) --------------------------------------------------------------

VALID = {
    "slug": "studio-ana",
    "name": "Studio Ana",
    "country": "BR",
    "owner_email": "ana@exemplo.com",
    "owner_name": "Ana",
}


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("slug", "Studio-Ana"),
        ("slug", "ab"),
        ("slug", "studio_ana"),
        ("slug", "-ana"),
        ("slug", "api"),
        ("country", "AR"),
        ("owner_email", "sem-arroba"),
        ("name", "  "),
    ],
)
def test_create_tenant_rejects_invalid_input(field, value):
    settings = Settings(database_admin_url="postgresql+psycopg://x@localhost:1/x")

    with pytest.raises(ProvisioningError):
        create_tenant(settings, **{**VALID, field: value})


def test_create_tenant_rejects_unknown_timezone():
    settings = Settings(database_admin_url="postgresql+psycopg://x@localhost:1/x")

    with pytest.raises(ProvisioningError, match="fuso"):
        create_tenant(settings, **VALID, timezone="America/Atlantida")


def test_create_tenant_rejects_dsn_ref_outside_the_pattern():
    settings = Settings(database_admin_url="postgresql+psycopg://x@localhost:1/x")

    with pytest.raises(ProvisioningError):
        create_tenant(settings, **VALID, dsn_ref="DATABASE_ADMIN_URL")


def test_seed_demo_is_refused_in_production():
    with pytest.raises(ProvisioningError, match="produção"):
        seed_demo(production_settings(), VERTICAL)


# --- com banco ---------------------------------------------------------------------------


def _admin(db_settings):
    return create_engine(db_settings.database_admin_url, poolclass=NullPool)


def test_created_salon_has_owner_with_argon2_password(db_settings, tenants):
    created = tenants["alpha"]
    databases = Databases(db_settings)

    with tenant_session(databases, load_tenant(databases, "alpha")) as session:
        owner = session.query(User).filter_by(email="dono@alpha.test").one()

    assert owner.email == "dono@alpha.test"
    assert owner.password_hash.startswith("$argon2id$")
    assert verify_password(owner.password_hash, created.owner_password)
    assert owner.must_change_password is True


def test_country_defaults(tenants):
    alpha, beta = tenants["alpha"].tenant, tenants["beta"].tenant

    assert (alpha.locale, alpha.timezone, alpha.currency) == ("pt-BR", "America/Sao_Paulo", "BRL")
    assert (beta.locale, beta.timezone, beta.currency) == ("es", "America/Asuncion", "PYG")


def test_duplicate_slug_is_refused(db_settings, tenants):
    with pytest.raises(ProvisioningError, match="já existe"):
        create_tenant(db_settings, **{**VALID, "slug": "alpha"})


def test_failed_creation_leaves_nothing_behind(db_settings, tenants, monkeypatch):
    def broken_migration(*_args):
        raise RuntimeError("migração quebrada")

    monkeypatch.setattr(provisioning, "upgrade_tenant", broken_migration)

    with pytest.raises(RuntimeError):
        create_tenant(db_settings, **{**VALID, "slug": "quebrado"})

    with _admin(db_settings).connect() as conn:
        assert conn.execute(text("SELECT to_regnamespace('t_quebrado')")).scalar() is None
        assert not conn.execute(text("SELECT 1 FROM public.tenants WHERE slug='quebrado'")).first()
        assert not conn.execute(
            text("SELECT 1 FROM pg_roles WHERE rolname = 'spbella_test_t_quebrado'")
        ).first()


def test_migrate_all_reaches_head_on_every_salon(db_settings, tenants):
    results = {r.slug: r for r in migrate_tenants(db_settings)}

    for slug in ("alpha", "beta", "gamma"):
        assert results[slug].error is None
        assert results[slug].after == tenant_head()


def test_migrate_continues_when_one_salon_fails(db_settings, tenants, monkeypatch):
    real_upgrade = provisioning.upgrade_tenant

    def flaky(admin_url, schema):
        if schema == "t_beta":
            raise RuntimeError("falha simulada")
        real_upgrade(admin_url, schema)

    monkeypatch.setattr(provisioning, "upgrade_tenant", flaky)

    results = {r.slug: r for r in migrate_tenants(db_settings)}

    assert "falha simulada" in results["beta"].error
    assert results["alpha"].error is None
    assert results["gamma"].error is None


def test_migrate_reports_unknown_slug(db_settings, tenants):
    results = migrate_tenants(db_settings, ["alpha", "fantasma"])

    assert {r.slug: r.error for r in results} == {"fantasma": "salão não encontrado", "alpha": None}


def test_only_one_migration_runs_at_a_time(db_settings, tenants):
    with _admin(db_settings).connect() as conn:
        conn.execute(text("SELECT pg_advisory_lock(:k)"), {"k": MIGRATION_LOCK_KEY})
        try:
            with pytest.raises(ProvisioningError, match="em andamento"):
                migrate_tenants(db_settings)
        finally:
            conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": MIGRATION_LOCK_KEY})


def test_list_shows_revision_of_each_salon(db_settings, tenants):
    listed = {t["slug"]: t for t in list_tenants(db_settings)}

    assert listed["alpha"]["revision"] == tenant_head()
    assert listed["gamma"]["dsn_ref"] == "TENANT_DSN_DEDICATED"


def test_seed_demo_creates_two_salons_once(db_settings, tenants):
    # Outro teste pode já ter criado a demonstração antes; o que importa: depois de rodar,
    # os dois salões existem, e rodar de novo não cria nada.
    seed_demo(db_settings, VERTICAL)
    second = seed_demo(db_settings, VERTICAL)

    slugs = {t["slug"] for t in list_tenants(db_settings)}
    assert {"studio-bella", "salon-asuncion"} <= slugs
    assert second == []
    databases = Databases(db_settings)
    with tenant_session(databases, load_tenant(databases, "salon-asuncion")) as session:
        people = {u.role: u for u in session.query(User)}
    # um acesso de cada perfil, para mostrar as três visões ao cliente (SAL-02)
    assert set(people) == {"owner", "reception", "professional"}
    assert people["reception"].email == "recepcion@salon-asuncion.demo"
    for user in people.values():
        assert verify_password(user.password_hash, DEMO_PASSWORD)
        assert user.must_change_password is False


def test_cli_migrate_returns_error_code_on_failure(db_settings, tenants, monkeypatch, capsys):
    monkeypatch.setattr(cli, "get_settings", lambda: db_settings)
    monkeypatch.setattr(
        provisioning, "upgrade_tenant", lambda *_: (_ for _ in ()).throw(RuntimeError("x"))
    )

    assert cli.main(["tenants", "migrate", "--slug", "alpha"]) == 1
    assert "1 com erro" in capsys.readouterr().out


def test_cli_create_prints_temporary_password_once(db_settings, tenants, monkeypatch, capsys):
    monkeypatch.setattr(cli, "get_settings", lambda: db_settings)

    code = cli.main(
        ["tenants", "create", "--slug", "via-cli", "--name", "Via CLI", "--country", "PY",
         "--owner-email", "Dona@Via-Cli.test", "--owner-name", "Dona"]
    )  # fmt: skip

    out = capsys.readouterr().out
    assert code == 0
    assert "dona@via-cli.test" in out
    assert "Senha provisória" in out


# --- SAL-01: plano, ganchos da vertical, tempo -------------------------------------------


def test_plan_must_be_known():
    settings = Settings(database_admin_url="postgresql+psycopg://x@localhost:1/x")

    with pytest.raises(ProvisioningError, match="plano"):
        create_tenant(settings, **VALID, plan="premium")


def test_plan_defaults_to_base_and_is_stored(db_settings, tenants):
    created = create_tenant(db_settings, **{**VALID, "slug": "com-whatsapp"}, plan="whatsapp_api")

    with _admin(db_settings).connect() as conn:
        plans = dict(conn.execute(text("SELECT slug, plan FROM public.tenants")).all())
    assert plans["alpha"] == "base"
    assert plans["com-whatsapp"] == "whatsapp_api"
    assert created.tenant.plan == "whatsapp_api"


def _vertical(seed) -> Vertical:
    return Vertical(name="teste", api_title="t", api_description="t", seed_tenant=seed)


def test_vertical_seed_runs_inside_the_new_tenant(db_settings, tenants):
    seen = {}

    def seed(session, tenant):
        seen["user"] = session.execute(text("SELECT current_user")).scalar()
        seen["owners"] = session.query(User).filter_by(role="owner").count()

    created = create_tenant(db_settings, **{**VALID, "slug": "com-seed"}, vertical=_vertical(seed))

    assert seen == {"user": created.tenant.role, "owners": 1}  # já vê o dono criado


def test_failing_vertical_seed_undoes_the_whole_tenant(db_settings, tenants):
    def broken_seed(session, tenant):
        raise RuntimeError("seed quebrado")

    with pytest.raises(RuntimeError, match="seed quebrado"):
        create_tenant(
            db_settings, **{**VALID, "slug": "seed-ruim"}, vertical=_vertical(broken_seed)
        )

    with _admin(db_settings).connect() as conn:
        assert conn.execute(text("SELECT to_regnamespace('t_seed_ruim')")).scalar() is None
        assert not conn.execute(text("SELECT 1 FROM public.tenants WHERE slug='seed-ruim'")).first()


def test_create_tenant_takes_less_than_a_minute(db_settings, tenants):
    """Critério de aceite do SAL-01."""
    start = time.perf_counter()
    create_tenant(db_settings, **{**VALID, "slug": "cronometrado"}, vertical=VERTICAL)
    elapsed = time.perf_counter() - start

    assert elapsed < 60, f"levou {elapsed:.1f}s"


def test_tenant_migrations_have_one_branch_per_module():
    names = [d.name for d in tenant_version_dirs()]

    assert names == ["core", "spbella"]
    script = ScriptDirectory.from_config(alembic_config("tenant", ""))
    heads = script.get_heads()
    assert len(heads) == 2  # um por módulo
    core_head, salon_head = sorted(heads, key=lambda h: h.startswith("salon"))
    # O core nunca depende da vertical (o template é copiado sem a pasta spbella)...
    core_chain = {r.revision for r in script.iterate_revisions(core_head, "base")}
    assert not any(rev.startswith("salon") for rev in core_chain)
    # ...e a vertical declara de que parte do core precisa.
    salon_root = script.get_revision("salon_0001_service_prices")
    deps = salon_root.dependencies
    assert "0005_offerings" in ((deps,) if isinstance(deps, str) else deps)
    assert "spbella" in salon_root.branch_labels
    assert "core" in script.get_revision("0001_users").branch_labels
