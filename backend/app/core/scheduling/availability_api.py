"""Horários livres para a equipe (sugestões no "Novo agendamento"). A página pública (SAL-11)
usa o mesmo cálculo (app/core/scheduling/availability.py)."""

import uuid
from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.core.accounts.auth import require_permission
from app.core.accounts.models import User
from app.core.accounts.permissions import Permission, permission_doc
from app.core.infra.errors import ApiError, error_responses
from app.core.infra.tenancy import DbSession, TenantDep
from app.core.scheduling.availability import free_slots
from app.core.scheduling.models import Offering

router = APIRouter(prefix="/t/{slug}/availability", tags=["Agenda"])


class FreeSlot(BaseModel):
    starts_at: datetime = Field(description="Início em UTC.")
    provider_ids: list[uuid.UUID] = Field(description="Quem está livre nesse horário.")


class AvailabilityOut(BaseModel):
    date: date
    timezone: str
    offering_id: uuid.UUID
    duration_min: int
    slots: list[FreeSlot]


@router.get(
    "",
    summary="Horários livres",
    description=(
        "Horários em que dá para marcar o serviço no dia (data local): jornada − bloqueios − "
        "agendamentos ativos, respeitando a duração do serviço e o intervalo mínimo entre "
        "atendimentos (Configurações). O serviço precisa caber inteiro numa faixa da jornada "
        "(não atravessa o almoço). Sem `provider_id`, junta todos os profissionais que fazem o "
        'serviço ("sem preferência").'
    ),
    response_model=AvailabilityOut,
    responses=error_responses(401, 403, 404, 422),
    openapi_extra=permission_doc(Permission.AGENDA_MANAGE),
)
def get_availability(
    tenant: TenantDep,
    db: DbSession,
    _user: Annotated[User, require_permission(Permission.AGENDA_MANAGE)],
    offering_id: Annotated[uuid.UUID, Query()],
    day: Annotated[date, Query(alias="date", description="Data local (AAAA-MM-DD).")],
    provider_id: Annotated[uuid.UUID | None, Query()] = None,
) -> AvailabilityOut:
    offering = db.get(Offering, offering_id)
    if offering is None or not offering.is_active:
        raise ApiError(422, "unknown_offering", "Serviço não encontrado ou desativado")
    slots = free_slots(
        db,
        tenant,
        offering=offering,
        day=day,
        provider_ids=[provider_id] if provider_id else None,
    )
    grouped: dict[datetime, list[uuid.UUID]] = {}
    for slot in slots:
        grouped.setdefault(slot.starts_at, []).append(slot.provider_id)
    return AvailabilityOut(
        date=day,
        timezone=tenant.timezone,
        offering_id=offering.id,
        duration_min=offering.duration_min,
        slots=[FreeSlot(starts_at=s, provider_ids=p) for s, p in grouped.items()],
    )
