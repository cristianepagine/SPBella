"""Operações administrativas: preparar o banco, criar tenants, migrar todos, demonstração.

No SPBella, "tenant" = salão. O que cada vertical acrescenta (dados iniciais, demonstração)
chega pelo objeto `Vertical` (app/core/vertical.py).

Rodam com o papel ADMINISTRADOR (DATABASE_ADMIN_URL), nunca pela API.

Papéis no Postgres:
- <papel da aplicação> (usuário de DATABASE_URL): LOGIN, NOINHERIT. Lê public.tenants e é membro
  de todos os papéis de salão, mas só usa os privilégios deles depois de SET ROLE.
- <prefixo>t_<slug> (um por salão): NOLOGIN. Acesso de leitura e escrita às tabelas do próprio
  schema e a mais nada.
- O administrador é dono dos schemas e das tabelas; os papéis de salão não podem alterar estrutura.
"""

import uuid
from dataclasses import dataclass
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from psycopg import sql
from sqlalchemy import Connection, Engine, create_engine, make_url, text
from sqlalchemy.pool import NullPool

from app.core.accounts.models import User
from app.core.infra.config import Settings
from app.core.infra.db import Databases, resolve_dsn_ref
from app.core.infra.migrations import upgrade_public, upgrade_tenant
from app.core.infra.security import (
    generate_temporary_password,
    hash_password,
    is_valid_email,
    normalize_email,
)
from app.core.infra.tenancy import (
    TenantContext,
    is_valid_slug,
    role_for,
    schema_for,
    tenant_session,
)
from app.core.vertical import CORE_ONLY, Vertical

COUNTRY_DEFAULTS = {
    "BR": {"locale": "pt-BR", "timezone": "America/Sao_Paulo", "currency": "BRL"},
    "PY": {"locale": "es", "timezone": "America/Asuncion", "currency": "PYG"},
}
MIGRATION_LOCK_KEY = 7_412_026_001  # chave do advisory lock de "tenants migrate"
PLANS = ("base", "whatsapp_api")

DEMO_PASSWORD = "demo-spbella"  # noqa: S105 - só para os tenants de demonstração


class ProvisioningError(Exception):
    """Erro esperado, com mensagem para quem está operando a CLI."""


@dataclass(frozen=True)
class CreatedTenant:
    tenant: TenantContext
    owner_email: str
    owner_password: str


@dataclass(frozen=True)
class MigrationResult:
    slug: str
    before: str | None
    after: str | None
    error: str | None = None


# --- utilitários -------------------------------------------------------------------------


def _admin_engine(url: str) -> Engine:
    return create_engine(url, poolclass=NullPool, isolation_level="AUTOCOMMIT")


def _run(conn: Connection, query: sql.Composable, params: tuple | None = None) -> list[tuple]:
    """Executa DDL com identificadores escapados pelo psycopg (sql.Identifier / sql.Literal)."""
    with conn.connection.driver_connection.cursor() as cursor:
        cursor.execute(query, params)
        return cursor.fetchall() if cursor.description else []


def _role_exists(conn: Connection, role: str) -> bool:
    return bool(_run(conn, sql.SQL("SELECT 1 FROM pg_roles WHERE rolname = %s"), (role,)))


def _admin_url(settings: Settings) -> str:
    if not settings.database_admin_url:
        raise ProvisioningError("defina DATABASE_ADMIN_URL (papel administrador) no .env")
    return settings.database_admin_url


def _ensure_app_role(conn: Connection, app_url: str) -> str:
    """Cria (ou atualiza) o papel da aplicação e libera a conexão ao banco atual."""
    url = make_url(app_url)
    role = url.username
    if not role:
        raise ProvisioningError("DATABASE_URL precisa ter usuário")
    verb = "ALTER" if _role_exists(conn, role) else "CREATE"
    query = sql.SQL(verb + " ROLE {} WITH LOGIN NOINHERIT").format(sql.Identifier(role))
    if url.password:
        query = query + sql.SQL(" PASSWORD {}").format(sql.Literal(url.password))
    _run(conn, query)
    database = _run(conn, sql.SQL("SELECT current_database()"))[0][0]
    _run(
        conn,
        sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
            sql.Identifier(database), sql.Identifier(role)
        ),
    )
    return role


def _grant_tenant_tables(conn: Connection, schema: str, role: str) -> None:
    """Dá ao papel do salão leitura e escrita nas tabelas do schema (roda após cada migração).

    Restrições extras por tabela (ex.: log de auditoria só aceita INSERT) são feitas com
    trigger na própria migração, porque este GRANT é reaplicado a cada migração.
    """
    s, r = sql.Identifier(schema), sql.Identifier(role)
    _run(
        conn,
        sql.SQL("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA {} TO {}").format(
            s, r
        ),
    )
    _run(conn, sql.SQL("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA {} TO {}").format(s, r))
    _run(conn, sql.SQL("REVOKE ALL ON TABLE {}.alembic_version FROM {}").format(s, r))


def _tenant_revision(conn: Connection, schema: str) -> str | None:
    table = sql.Identifier(schema, "alembic_version")
    exists = _run(
        conn,
        sql.SQL("SELECT to_regclass(%s)"),
        (table.as_string(conn.connection.driver_connection),),
    )
    if exists[0][0] is None:
        return None
    rows = _run(conn, sql.SQL("SELECT version_num FROM {}").format(table))
    return rows[0][0] if rows else None


def _target_urls(settings: Settings, dsn_ref: str | None) -> tuple[str, str]:
    """(url admin, url da aplicação) do banco onde o salão mora."""
    if dsn_ref:
        try:
            return resolve_dsn_ref(dsn_ref, admin=True), resolve_dsn_ref(dsn_ref)
        except (ValueError, RuntimeError) as exc:
            raise ProvisioningError(str(exc)) from exc
    return _admin_url(settings), settings.database_url


# --- comandos ----------------------------------------------------------------------------


def init_database(settings: Settings) -> None:
    """Prepara o banco principal: papel da aplicação + migrações do public. Pode rodar sempre."""
    admin_url = _admin_url(settings)
    with _admin_engine(admin_url).connect() as conn:
        app_role = _ensure_app_role(conn, settings.database_url)
        _run(conn, sql.SQL("REVOKE CREATE ON SCHEMA public FROM PUBLIC"))
    upgrade_public(admin_url)
    with _admin_engine(admin_url).connect() as conn:
        role = sql.Identifier(app_role)
        _run(conn, sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(role))
        _run(conn, sql.SQL("GRANT SELECT ON public.tenants TO {}").format(role))


def create_tenant(
    settings: Settings,
    *,
    slug: str,
    name: str,
    country: str,
    owner_email: str,
    owner_name: str,
    owner_password: str | None = None,
    dsn_ref: str | None = None,
    locale: str | None = None,
    timezone: str | None = None,
    currency: str | None = None,
    plan: str = "base",
    vertical: Vertical = CORE_ONLY,
) -> CreatedTenant:
    """Cria schema + papel + migrações + usuário dono + dados iniciais da vertical.
    Se algo falhar, desfaz tudo."""
    if not is_valid_slug(slug):
        raise ProvisioningError(
            "slug inválido: use 3 a 40 letras minúsculas, números e hífen (ex.: studio-ana)"
        )
    if country not in COUNTRY_DEFAULTS:
        raise ProvisioningError("país deve ser BR ou PY")
    owner_email = normalize_email(owner_email)
    if not is_valid_email(owner_email):
        raise ProvisioningError("e-mail do dono inválido")
    if not name.strip() or not owner_name.strip():
        raise ProvisioningError("nome do salão e do dono são obrigatórios")
    if plan not in PLANS:
        raise ProvisioningError(f"plano deve ser um de: {', '.join(PLANS)}")

    defaults = COUNTRY_DEFAULTS[country]
    locale = locale or defaults["locale"]
    timezone = timezone or defaults["timezone"]
    currency = currency or defaults["currency"]
    try:
        ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ProvisioningError(f"fuso horário desconhecido: {timezone}") from exc

    schema = schema_for(slug)
    role = role_for(slug, settings.tenant_role_prefix)
    control_admin = _admin_url(settings)
    target_admin, target_app = _target_urls(settings, dsn_ref)

    tenant = TenantContext(
        id=uuid.uuid4(),
        slug=slug,
        name=name.strip(),
        schema=schema,
        role=role,
        dsn_ref=dsn_ref,
        country=country,
        locale=locale,
        timezone=timezone,
        currency=currency,
        status="active",
        plan=plan,
    )

    with _admin_engine(control_admin).connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM public.tenants WHERE slug = :slug OR schema_name = :schema"),
            {"slug": slug, "schema": schema},
        ).first()
        if exists:
            raise ProvisioningError(f"já existe um salão com o slug {slug}")
        conn.execute(
            text(
                "INSERT INTO public.tenants (id, slug, name, schema_name, db_role, dsn_ref,"
                " country, locale, timezone, currency, plan, status) VALUES (:id, :slug, :name,"
                " :schema, :role, :dsn_ref, :country, :locale, :timezone, :currency, :plan,"
                " 'provisioning')"
            ),
            {
                "id": tenant.id, "slug": slug, "name": tenant.name, "schema": schema, "role": role,
                "dsn_ref": dsn_ref, "country": country, "locale": locale, "timezone": timezone,
                "currency": currency, "plan": plan,
            },
        )  # fmt: skip

    try:
        with _admin_engine(target_admin).connect() as conn:
            if _run(conn, sql.SQL("SELECT 1 FROM pg_namespace WHERE nspname = %s"), (schema,)):
                raise ProvisioningError(f"o schema {schema} já existe nesse banco")
            app_role = _ensure_app_role(conn, target_app)
            s, r = sql.Identifier(schema), sql.Identifier(role)
            if not _role_exists(conn, role):
                _run(conn, sql.SQL("CREATE ROLE {} NOLOGIN NOINHERIT").format(r))
            _run(conn, sql.SQL("CREATE SCHEMA {}").format(s))
            _run(conn, sql.SQL("REVOKE ALL ON SCHEMA {} FROM PUBLIC").format(s))
            _run(conn, sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(s, r))
            _run(conn, sql.SQL("GRANT {} TO {}").format(r, sql.Identifier(app_role)))

        upgrade_tenant(target_admin, schema)
        with _admin_engine(target_admin).connect() as conn:
            _grant_tenant_tables(conn, schema, role)

        password = owner_password or generate_temporary_password()
        databases = Databases(settings)
        try:
            # Cria o dono pelo mesmo caminho da API (papel do salão), o que já testa as permissões.
            with tenant_session(databases, tenant) as session:
                session.add(
                    User(
                        name=owner_name.strip(),
                        email=owner_email,
                        password_hash=hash_password(password),
                        role="owner",
                        must_change_password=owner_password is None,
                    )
                )
                # Na mesma transação: se os dados iniciais falharem, nada fica pela metade.
                if vertical.seed_tenant:
                    vertical.seed_tenant(session, tenant)
        finally:
            databases.dispose()

        with _admin_engine(control_admin).connect() as conn:
            conn.execute(
                text("UPDATE public.tenants SET status = 'active' WHERE id = :id"),
                {"id": tenant.id},
            )
    except Exception:
        _rollback_tenant(control_admin, target_admin, tenant)
        raise

    return CreatedTenant(tenant=tenant, owner_email=owner_email, owner_password=password)


def _rollback_tenant(control_admin: str, target_admin: str, tenant: TenantContext) -> None:
    with _admin_engine(target_admin).connect() as conn:
        _run(
            conn, sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(tenant.schema))
        )
        if _role_exists(conn, tenant.role):
            _run(conn, sql.SQL("DROP OWNED BY {}").format(sql.Identifier(tenant.role)))
            _run(conn, sql.SQL("DROP ROLE {}").format(sql.Identifier(tenant.role)))
    with _admin_engine(control_admin).connect() as conn:
        conn.execute(text("DELETE FROM public.tenants WHERE id = :id"), {"id": tenant.id})


def migrate_tenants(settings: Settings, slugs: list[str] | None = None) -> list[MigrationResult]:
    """Aplica as migrações dos salões, um por vez. Se um falhar, segue para o próximo.

    O código novo precisa funcionar com salões ainda na versão anterior (migrações no estilo
    "expandir, depois contrair"), porque durante o lote há salões em versões diferentes.
    """
    control_admin = _admin_url(settings)
    results: list[MigrationResult] = []
    with _admin_engine(control_admin).connect() as lock_conn:
        got_lock = lock_conn.execute(
            text("SELECT pg_try_advisory_lock(:key)"), {"key": MIGRATION_LOCK_KEY}
        ).scalar()
        if not got_lock:
            raise ProvisioningError("já existe uma migração de salões em andamento")
        try:
            query = (
                "SELECT slug, schema_name, db_role, dsn_ref FROM public.tenants"
                " WHERE status IN ('active', 'suspended')"
            )
            params: dict = {}
            if slugs:
                query += " AND slug = ANY(:slugs)"
                params["slugs"] = slugs
            rows = lock_conn.execute(text(query + " ORDER BY slug"), params).all()

            found = {row.slug for row in rows}
            results += [
                MigrationResult(slug, None, None, "salão não encontrado")
                for slug in slugs or []
                if slug not in found
            ]

            for row in rows:
                before = None
                try:
                    target_admin, _ = _target_urls(settings, row.dsn_ref)
                    with _admin_engine(target_admin).connect() as conn:
                        before = _tenant_revision(conn, row.schema_name)
                    upgrade_tenant(target_admin, row.schema_name)
                    with _admin_engine(target_admin).connect() as conn:
                        _grant_tenant_tables(conn, row.schema_name, row.db_role)
                        after = _tenant_revision(conn, row.schema_name)
                    results.append(MigrationResult(row.slug, before, after))
                except Exception as exc:  # noqa: BLE001 - registra e segue para o próximo salão
                    error = f"{type(exc).__name__}: {str(exc).splitlines()[0][:200]}"
                    results.append(MigrationResult(row.slug, before, before, error))
        finally:
            lock_conn.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": MIGRATION_LOCK_KEY})
    return results


def list_tenants(settings: Settings) -> list[dict]:
    control_admin = _admin_url(settings)
    with _admin_engine(control_admin).connect() as conn:
        rows = conn.execute(
            text(
                "SELECT slug, name, country, plan, status, schema_name, dsn_ref"
                " FROM public.tenants ORDER BY slug"
            )
        ).all()
    result = []
    for row in rows:
        try:
            target_admin, _ = _target_urls(settings, row.dsn_ref)
            with _admin_engine(target_admin).connect() as conn:
                revision = _tenant_revision(conn, row.schema_name)
        except Exception as exc:  # noqa: BLE001
            revision = f"? ({type(exc).__name__})"
        result.append({**row._asdict(), "revision": revision})
    return result


def seed_demo(settings: Settings, vertical: Vertical) -> list[CreatedTenant]:
    """Cria os tenants de demonstração da vertical, se ainda não existirem.
    Proibido em produção."""
    if settings.app_env == "production":
        raise ProvisioningError("dados de demonstração não podem ser criados em produção")
    with _admin_engine(_admin_url(settings)).connect() as conn:
        existing = set(conn.execute(text("SELECT slug FROM public.tenants")).scalars())

    created = []
    for demo in vertical.demo_tenants:
        if demo.slug in existing:
            continue
        result = create_tenant(
            settings,
            slug=demo.slug,
            name=demo.name,
            country=demo.country,
            owner_email=demo.owner_email,
            owner_name=demo.owner_name,
            owner_password=DEMO_PASSWORD,
            vertical=vertical,
        )
        if vertical.seed_demo:
            databases = Databases(settings)
            try:
                with tenant_session(databases, result.tenant) as session:
                    vertical.seed_demo(session, result.tenant)
            finally:
                databases.dispose()
        created.append(result)
    return created
