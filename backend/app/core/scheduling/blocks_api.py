"""Bloqueios (SAL-10): de um profissional ou do estabelecimento inteiro; dias inteiros (férias,
feriado) ou um intervalo de horas (consulta médica, reunião). Bloqueado não aparece como livre
na agenda nem na página pública.

O almoço fixo de todo dia é feito na jornada (duas faixas no dia), não com bloqueio.
"""

import uuid
from datetime import UTC, date, datetime, time, timedelta
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Response
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.accounts.auth import require_permission
from app.core.accounts.models import User
from app.core.accounts.permissions import Permission, permission_doc
from app.core.customers.models import Customer
from app.core.infra.errors import ApiError, FieldError, error_responses
from app.core.infra.logging import log
from app.core.infra.tenancy import DbSession, TenantContext, TenantDep
from app.core.scheduling.models import ACTIVE_STATUSES, Appointment, Provider, TimeOff

router = APIRouter(prefix="/t/{slug}/blocks", tags=["Agenda"])

BlockManager = Annotated[User, require_permission(Permission.TIME_OFF_MANAGE)]
DOC = permission_doc(Permission.TIME_OFF_MANAGE)
TIME_PATTERN = r"^([01]\d|2[0-3]):[0-5]\d$"


class NewBlock(BaseModel):
    provider_id: uuid.UUID | None = Field(
        default=None, description="Profissional bloqueado; `null` = o estabelecimento inteiro."
    )
    start_date: date = Field(description="Primeiro dia (data local).", examples=["2026-12-25"])
    end_date: date | None = Field(
        default=None, description="Último dia, inclusive (só para dias inteiros)."
    )
    start_time: str | None = Field(
        default=None, pattern=TIME_PATTERN, description="Início `HH:MM` (só para horas)."
    )
    end_time: str | None = Field(
        default=None, pattern=TIME_PATTERN, description="Fim `HH:MM` (só para horas)."
    )
    reason: str | None = Field(default=None, max_length=120, examples=["Feriado"])


class Conflict(BaseModel):
    appointment_id: uuid.UUID
    provider_id: uuid.UUID
    customer_name: str
    starts_at: datetime


class BlockOut(BaseModel):
    id: uuid.UUID
    provider_id: uuid.UUID | None
    starts_at: datetime
    ends_at: datetime
    reason: str | None
    conflicts: list[Conflict] = Field(
        description="Agendamentos ativos que já estavam marcados no período bloqueado. Nada é "
        "cancelado sozinho: a equipe decide se remarca ou cancela."
    )


def _field_error(field: str, code: str) -> ApiError:
    return ApiError(
        422, "validation_error", "Dados inválidos", fields=[FieldError(field=field, code=code)]
    )


def _parse(hhmm: str) -> time:
    hours, minutes = map(int, hhmm.split(":"))
    return time(hours, minutes)


def _interval(payload: NewBlock, tenant: TenantContext) -> tuple[datetime, datetime]:
    zone = ZoneInfo(tenant.timezone)
    hours = payload.start_time is not None or payload.end_time is not None
    if hours:
        if payload.start_time is None or payload.end_time is None:
            raise _field_error("end_time", "start_and_end_required")
        if payload.end_date not in (None, payload.start_date):
            raise _field_error("end_date", "hours_block_is_one_day")
        start, end = _parse(payload.start_time), _parse(payload.end_time)
        if start.minute % 5 or end.minute % 5:
            raise _field_error("start_time", "invalid_time_step")
        if start >= end:
            raise _field_error("end_time", "start_after_end")
        first = datetime.combine(payload.start_date, start, tzinfo=zone)
        last = datetime.combine(payload.start_date, end, tzinfo=zone)
    else:
        end_date = payload.end_date or payload.start_date
        if end_date < payload.start_date:
            raise _field_error("end_date", "end_before_start")
        if (end_date - payload.start_date).days > 365:
            raise _field_error("end_date", "too_long")
        first = datetime.combine(payload.start_date, time(0), tzinfo=zone)
        last = datetime.combine(end_date + timedelta(days=1), time(0), tzinfo=zone)
    return first.astimezone(UTC), last.astimezone(UTC)


@router.post(
    "",
    summary="Bloquear horário",
    description=(
        "Dois jeitos:\n"
        "- **Dias inteiros:** `start_date` e, se for mais de um dia, `end_date`.\n"
        "- **Intervalo de horas num dia:** `start_date`, `start_time` e `end_time`.\n\n"
        "`provider_id` vazio bloqueia o estabelecimento inteiro (feriado). A resposta traz em "
        "`conflicts` os agendamentos que já estavam marcados no período.\n\n"
        "`422` com `fields[0].code`: `start_after_end`, `start_and_end_required`, "
        "`hours_block_is_one_day`, `invalid_time_step`, `end_before_start`, `too_long`, "
        "`unknown_provider`."
    ),
    status_code=201,
    response_model=BlockOut,
    responses=error_responses(401, 403, 404, 422),
    openapi_extra=DOC,
)
def create_block(
    payload: NewBlock, tenant: TenantDep, db: DbSession, user: BlockManager
) -> BlockOut:
    if payload.provider_id is not None and db.get(Provider, payload.provider_id) is None:
        raise _field_error("provider_id", "unknown_provider")
    starts_at, ends_at = _interval(payload, tenant)
    block = TimeOff(
        id=uuid.uuid4(),
        provider_id=payload.provider_id,
        starts_at=starts_at,
        ends_at=ends_at,
        reason=(payload.reason or "").strip() or None,
    )
    db.add(block)

    query = (
        select(Appointment, Customer.name)
        .join(Customer, Customer.id == Appointment.customer_id)
        .where(
            Appointment.status.in_(ACTIVE_STATUSES),
            Appointment.starts_at < ends_at,
            Appointment.ends_at > starts_at,
        )
        .order_by(Appointment.starts_at)
    )
    if payload.provider_id is not None:
        query = query.where(Appointment.provider_id == payload.provider_id)
    conflicts = [
        Conflict(
            appointment_id=a.id,
            provider_id=a.provider_id,
            customer_name=name,
            starts_at=a.starts_at,
        )
        for a, name in db.execute(query)
    ]
    db.flush()
    log.info(
        "block_created",
        tenant_id=str(tenant.id),
        user_id=str(user.id),
        block_id=str(block.id),
        conflicts=len(conflicts),
    )
    return BlockOut(
        id=block.id,
        provider_id=block.provider_id,
        starts_at=block.starts_at,
        ends_at=block.ends_at,
        reason=block.reason,
        conflicts=conflicts,
    )


@router.delete(
    "/{block_id}",
    summary="Remover bloqueio",
    description="O período volta a seguir a jornada normal.",
    status_code=204,
    responses=error_responses(401, 403, 404),
    openapi_extra=DOC,
)
def delete_block(block_id: uuid.UUID, db: DbSession, _user: BlockManager) -> Response:
    block = db.get(TimeOff, block_id)
    if block is None:
        raise ApiError(404, "not_found", "Bloqueio não encontrado")
    db.delete(block)
    return Response(status_code=204)
