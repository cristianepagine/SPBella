"""Ponto de extensão do template.

O core (app/core) é genérico: salões, login, perfis, clientes, agenda, notificações, relatórios.
Cada sistema construído sobre ele (hoje: salão; amanhã: clínica, pet shop...) é uma "vertical",
que se descreve com um objeto `Vertical` e é ligada ao core em app/registry.py.

Regra: o core nunca importa nada de uma vertical (tests/test_architecture.py garante).
"""

import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from fastapi import APIRouter
from sqlalchemy.orm import Session

from app.core.infra.tenancy import TenantContext

# Recebe a sessão JÁ DENTRO do tenant (papel e schema do tenant) e o contexto dele.
TenantSeed = Callable[[Session, TenantContext], None]
# Dados extras dos itens agendáveis na página pública (ex.: preço do serviço no salão).
OfferingExtras = Callable[[Session, Sequence[uuid.UUID]], dict[uuid.UUID, dict[str, int | str]]]


@dataclass(frozen=True)
class DemoTenant:
    slug: str
    name: str
    country: str
    owner_email: str
    owner_name: str


@dataclass(frozen=True)
class Vertical:
    name: str
    api_title: str
    api_description: str
    routers: Sequence[APIRouter] = ()
    openapi_tags: Sequence[dict] = ()
    # Dados iniciais de TODO tenant novo (ex.: serviços de exemplo do salão).
    seed_tenant: TenantSeed | None = None
    # Tenants de demonstração (`tenants seed-demo`) e os dados extras deles.
    demo_tenants: Sequence[DemoTenant] = field(default_factory=tuple)
    seed_demo: TenantSeed | None = None
    # Campo `extras` de cada item no catálogo da página pública (`GET /booking/catalog`).
    public_offering_extras: OfferingExtras | None = None


CORE_ONLY = Vertical(
    name="core",
    api_title="API",
    api_description="Núcleo sem vertical (usado em testes do core).",
)
