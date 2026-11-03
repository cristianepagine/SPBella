"""Isolamento entre salões (tenants). ESTE é o único ponto que abre sessão em um salão.

Cada salão tem um schema próprio (t_<slug>) e um papel próprio no Postgres, que só tem acesso a
esse schema. O papel da aplicação não acessa tabela de salão nenhuma por conta própria (NOINHERIT):
em cada transação ele faz

    SET LOCAL ROLE <papel do salão>;  SET LOCAL search_path = <schema do salão>;

Por serem LOCAL, os dois valem só até o fim da transação: a conexão volta limpa para o pool.
Mesmo que um bug monte uma consulta para outro schema, o banco nega a permissão.
"""

import re
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Path, Request
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.infra.db import Databases
from app.core.infra.errors import ApiError
from app.core.tenants.models import Tenant

SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
IDENTIFIER_PATTERN = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")
# Slugs que confundiriam URLs do app ou da página pública.
RESERVED_SLUGS = frozenset(
    {"admin", "api", "app", "assets", "docs", "health", "login", "public", "static", "www"}
)


def is_valid_slug(slug: str) -> bool:
    return 3 <= len(slug) <= 40 and bool(SLUG_PATTERN.match(slug)) and slug not in RESERVED_SLUGS


def schema_for(slug: str) -> str:
    return "t_" + slug.replace("-", "_")


def role_for(slug: str, prefix: str) -> str:
    return prefix + schema_for(slug)


@dataclass(frozen=True)
class TenantContext:
    id: uuid.UUID
    slug: str
    name: str
    schema: str
    role: str
    dsn_ref: str | None
    country: str
    locale: str
    timezone: str
    currency: str
    status: str
    plan: str = "base"

    @classmethod
    def from_model(cls, tenant: Tenant) -> "TenantContext":
        return cls(
            id=tenant.id,
            slug=tenant.slug,
            name=tenant.name,
            schema=tenant.schema_name,
            role=tenant.db_role,
            dsn_ref=tenant.dsn_ref,
            country=tenant.country,
            locale=tenant.locale,
            timezone=tenant.timezone,
            currency=tenant.currency,
            status=tenant.status,
            plan=tenant.plan,
        )


def load_tenant(databases: Databases, slug: str) -> TenantContext | None:
    if not is_valid_slug(slug):
        return None
    with Session(databases.control) as session:
        tenant = session.scalar(select(Tenant).where(Tenant.slug == slug))
        return TenantContext.from_model(tenant) if tenant else None


@contextmanager
def tenant_session(databases: Databases, tenant: TenantContext) -> Iterator[Session]:
    """Sessão dentro do salão. Commit ao sair sem erro; rollback se houver exceção."""
    # Defesa extra: nomes vindos do banco só entram no SQL se forem identificadores simples.
    if not (IDENTIFIER_PATTERN.match(tenant.schema) and IDENTIFIER_PATTERN.match(tenant.role)):
        raise RuntimeError(f"identificadores inválidos para o tenant {tenant.id}")

    with Session(databases.for_tenant(tenant.dsn_ref), expire_on_commit=False) as session:
        with session.begin():
            session.execute(text(f'SET LOCAL ROLE "{tenant.role}"'))
            session.execute(
                text("SELECT set_config('search_path', :path, true)"),
                {"path": f'"{tenant.schema}"'},
            )
            yield session


# --- Dependências do FastAPI -------------------------------------------------------------


def get_tenant(
    request: Request,
    slug: Annotated[
        str,
        Path(description="Identificador do salão na URL.", examples=["studio-bella"]),
    ],
) -> TenantContext:
    tenant = load_tenant(request.app.state.databases, slug)
    # Salão inexistente, suspenso ou em criação: mesma resposta, para não revelar qual é o caso.
    if tenant is None or tenant.status != "active":
        raise ApiError(404, "tenant_not_found", "Salão não encontrado")
    # Guardado no pedido (e não no contexto do log): dependências síncronas rodam em outra
    # thread, e o que é gravado no contexto lá se perde. O log de acesso lê daqui.
    request.state.tenant_id = str(tenant.id)
    return tenant


def get_db(
    request: Request, tenant: Annotated[TenantContext, Depends(get_tenant)]
) -> Iterator[Session]:
    with tenant_session(request.app.state.databases, tenant) as session:
        yield session


TenantDep = Annotated[TenantContext, Depends(get_tenant)]
# scope="function": o commit acontece ANTES de a resposta sair. Se o commit falhar, o cliente
# recebe erro em vez de um "ok" falso.
DbSession = Annotated[Session, Depends(get_db, scope="function")]
