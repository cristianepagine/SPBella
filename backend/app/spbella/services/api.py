"""Serviços do salão (SAL-05): nome, duração e preço na moeda do estabelecimento."""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.accounts.auth import require_permission
from app.core.accounts.models import User
from app.core.accounts.permissions import Permission, permission_doc
from app.core.infra.errors import ApiError, FieldError, error_responses
from app.core.infra.tenancy import DbSession, TenantContext, TenantDep
from app.core.scheduling.models import DURATION_MAX_MIN, DURATION_STEP_MIN, Offering
from app.spbella.services.models import PRICE_MAX_MINOR, ServicePrice

router = APIRouter(prefix="/t/{slug}/services", tags=["Serviços"])

CatalogViewer = Annotated[User, require_permission(Permission.CATALOG_VIEW)]
CatalogManager = Annotated[User, require_permission(Permission.CATALOG_MANAGE)]

DURATION_DOC = (
    f"Minutos, de {DURATION_STEP_MIN} a {DURATION_MAX_MIN}, em múltiplos de {DURATION_STEP_MIN}."
)
PRICE_DOC = (
    "Na menor unidade da moeda do estabelecimento: centavos em BRL (`4590` = R$ 45,90), "
    "guaranis em PYG (`150000` = Gs. 150.000)."
)


class ServiceOut(BaseModel):
    id: uuid.UUID
    name: str = Field(examples=["Corte feminino"])
    duration_min: int = Field(description=DURATION_DOC, examples=[60])
    price_minor: int = Field(description=PRICE_DOC, examples=[8000])
    currency: Literal["BRL", "PYG"]
    is_active: bool = Field(description="Desativado não aparece para agendar.")
    updated_at: datetime


class NewService(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    duration_min: int = Field(description=DURATION_DOC)
    price_minor: int = Field(description=PRICE_DOC)


class ServiceChanges(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    duration_min: int | None = Field(default=None, description=DURATION_DOC)
    price_minor: int | None = Field(default=None, description=PRICE_DOC)
    is_active: bool | None = None


def _field_error(field: str, code: str) -> ApiError:
    return ApiError(
        422, "validation_error", "Dados inválidos", fields=[FieldError(field=field, code=code)]
    )


def _check(name: str | None, duration: int | None, price: int | None) -> None:
    if name is not None and not name.strip():
        raise _field_error("name", "string_too_short")
    if duration is not None and not (
        DURATION_STEP_MIN <= duration <= DURATION_MAX_MIN and duration % DURATION_STEP_MIN == 0
    ):
        raise _field_error("duration_min", "invalid_duration")
    if price is not None and not 0 <= price <= PRICE_MAX_MINOR:
        raise _field_error("price_minor", "invalid_price")


def _out(price: ServicePrice, tenant: TenantContext) -> ServiceOut:
    offering = price.offering
    return ServiceOut(
        id=offering.id,
        name=offering.name,
        duration_min=offering.duration_min,
        price_minor=price.price_minor,
        currency=tenant.currency,
        is_active=offering.is_active,
        updated_at=offering.updated_at,
    )


def _get(db: DbSession, service_id: uuid.UUID) -> ServicePrice:
    price = db.get(ServicePrice, service_id)
    if price is None:
        raise ApiError(404, "not_found", "Serviço não encontrado")
    return price


def add_service(db, *, name: str, duration_min: int, price_minor: int) -> ServicePrice:
    """Cria o item agendável (core) e o preço (salão). Usado pela rota e pelos exemplos."""
    _check(name, duration_min, price_minor)
    offering = Offering(id=uuid.uuid4(), name=name.strip(), duration_min=duration_min)
    db.add(offering)
    price = ServicePrice(offering=offering, price_minor=price_minor)
    db.add(price)
    return price


@router.get(
    "",
    summary="Listar serviços",
    description=(
        "Em ordem alfabética. Por padrão, só os ativos; `include_inactive=true` traz todos "
        "(para a tela de cadastro)."
    ),
    response_model=list[ServiceOut],
    responses=error_responses(401, 403, 404),
    openapi_extra=permission_doc(Permission.CATALOG_VIEW),
)
def list_services(
    tenant: TenantDep,
    db: DbSession,
    _user: CatalogViewer,
    include_inactive: Annotated[bool, Query()] = False,
) -> list[ServiceOut]:
    query = select(ServicePrice).join(ServicePrice.offering).order_by(Offering.name)
    if not include_inactive:
        query = query.where(Offering.is_active)
    return [_out(price, tenant) for price in db.scalars(query)]


@router.post(
    "",
    summary="Cadastrar serviço",
    description=(
        f"{PRICE_DOC}\n\n"
        "- `422` com `fields[0].code`: `invalid_duration`, `invalid_price` ou "
        "`string_too_short` (nome vazio)."
    ),
    status_code=201,
    response_model=ServiceOut,
    responses=error_responses(401, 403, 404, 422),
    openapi_extra=permission_doc(Permission.CATALOG_MANAGE),
)
def create_service(
    payload: NewService, tenant: TenantDep, db: DbSession, _user: CatalogManager
) -> ServiceOut:
    price = add_service(
        db, name=payload.name, duration_min=payload.duration_min, price_minor=payload.price_minor
    )
    db.flush()
    db.refresh(price.offering)
    return _out(price, tenant)


@router.patch(
    "/{service_id}",
    summary="Alterar ou desativar serviço",
    description=(
        "Só os campos enviados mudam. Serviços não são apagados: `is_active: false` tira o "
        "serviço da agenda e da página pública, mas agendamentos antigos continuam com ele. "
        "Mudar o preço não muda o de agendamentos já feitos (cada agendamento guarda o seu)."
    ),
    response_model=ServiceOut,
    responses=error_responses(401, 403, 404, 422),
    openapi_extra=permission_doc(Permission.CATALOG_MANAGE),
)
def change_service(
    service_id: uuid.UUID,
    payload: ServiceChanges,
    tenant: TenantDep,
    db: DbSession,
    _user: CatalogManager,
) -> ServiceOut:
    price = _get(db, service_id)
    _check(payload.name, payload.duration_min, payload.price_minor)
    offering = price.offering
    if payload.name is not None:
        offering.name = payload.name.strip()
    if payload.duration_min is not None:
        offering.duration_min = payload.duration_min
    if payload.is_active is not None:
        offering.is_active = payload.is_active
    if payload.price_minor is not None:
        price.price_minor = payload.price_minor
    db.flush()
    db.refresh(offering)
    return _out(price, tenant)
