"""Agendamentos pela equipe (SAL-09): criar, mover, mudar status (confirmar, atendido, faltou,
cancelar)."""

import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.accounts.auth import require_permission
from app.core.accounts.models import User
from app.core.accounts.permissions import Permission, permission_doc
from app.core.customers.models import Customer
from app.core.infra.errors import ApiError, error_responses
from app.core.infra.logging import log
from app.core.infra.tenancy import DbSession, TenantDep
from app.core.scheduling.booking import check_slot, flush_or_slot_taken, require_service_consent
from app.core.scheduling.models import ACTIVE_STATUSES, Appointment, Offering

router = APIRouter(prefix="/t/{slug}/appointments", tags=["Agenda"])

AgendaManager = Annotated[User, require_permission(Permission.AGENDA_MANAGE)]
DOC = permission_doc(Permission.AGENDA_MANAGE)
Status = Literal["scheduled", "confirmed", "completed", "no_show", "cancelled"]

CONFLICTS_DOC = (
    "- `409 slot_taken`: o profissional já tem alguém nesse horário (inclusive quando duas "
    "pessoas tentam o mesmo horário ao mesmo tempo: só uma consegue).\n"
    "- `409 outside_working_hours` / `409 provider_time_off` / `409 too_close` (sem o "
    "intervalo mínimo até outro atendimento): mande `allow_outside_hours: true` para encaixar "
    "mesmo assim (nunca vale por cima de outro cliente).\n"
    "- `409 customer_without_consent`: o cliente retirou a autorização de uso dos dados para "
    "atendimento.\n"
    "- `422 provider_cannot_do`, `unknown_provider`, `unknown_offering`, `unknown_customer`, "
    "`invalid_time_step` (minutos de 5 em 5)."
)


class AppointmentOut(BaseModel):
    id: uuid.UUID
    provider_id: uuid.UUID
    offering_id: uuid.UUID
    customer_id: uuid.UUID
    starts_at: datetime
    ends_at: datetime
    status: Status
    source: Literal["staff", "public"]


class NewAppointment(BaseModel):
    provider_id: uuid.UUID
    offering_id: uuid.UUID
    customer_id: uuid.UUID
    starts_at: datetime = Field(
        description="Início em UTC (ou com fuso). O fim é calculado pela duração do serviço.",
        examples=["2026-11-03T13:00:00Z"],
    )
    allow_outside_hours: bool = Field(
        default=False, description="Encaixe: aceita fora da jornada ou em folga."
    )


class MoveAppointment(BaseModel):
    starts_at: datetime | None = None
    provider_id: uuid.UUID | None = None
    offering_id: uuid.UUID | None = None
    allow_outside_hours: bool = False


class StatusChange(BaseModel):
    status: Status = Field(
        description="`confirmed`, `completed` (atendido), `no_show` (faltou), `cancelled`, "
        "ou `scheduled` (voltar a agendado)."
    )


def _out(a: Appointment) -> AppointmentOut:
    return AppointmentOut.model_validate(a, from_attributes=True)


def _offering(db: DbSession, offering_id: uuid.UUID) -> Offering:
    offering = db.get(Offering, offering_id)
    if offering is None or not offering.is_active:
        raise ApiError(422, "unknown_offering", "Serviço não encontrado ou desativado")
    return offering


def _get(db: DbSession, appointment_id: uuid.UUID) -> Appointment:
    appointment = db.get(Appointment, appointment_id)
    if appointment is None:
        raise ApiError(404, "not_found", "Agendamento não encontrado")
    return appointment


@router.post(
    "",
    summary="Marcar horário",
    description=f"Agenda um cliente com um profissional.\n\n{CONFLICTS_DOC}",
    status_code=201,
    response_model=AppointmentOut,
    responses=error_responses(401, 403, 404, 409, 422),
    openapi_extra=DOC,
)
def create_appointment(
    payload: NewAppointment, tenant: TenantDep, db: DbSession, user: AgendaManager
) -> AppointmentOut:
    customer = db.get(Customer, payload.customer_id)
    if customer is None:
        raise ApiError(422, "unknown_customer", "Cliente não encontrado")
    require_service_consent(customer)
    offering = _offering(db, payload.offering_id)
    ends_at = check_slot(
        db,
        tenant,
        provider_id=payload.provider_id,
        offering=offering,
        starts_at=payload.starts_at,
        allow_outside_hours=payload.allow_outside_hours,
    )
    appointment = Appointment(
        id=uuid.uuid4(),
        provider_id=payload.provider_id,
        offering_id=offering.id,
        customer_id=customer.id,
        starts_at=payload.starts_at.astimezone(UTC),
        ends_at=ends_at,
        status="scheduled",
        source="staff",
        created_by=user.id,
    )
    db.add(appointment)
    flush_or_slot_taken(db)
    log.info(
        "appointment_created",
        tenant_id=str(tenant.id),
        user_id=str(user.id),
        appointment_id=str(appointment.id),
    )
    return _out(appointment)


@router.patch(
    "/{appointment_id}",
    summary="Mover agendamento",
    description=(
        "Muda o horário, o profissional e/ou o serviço (o fim é recalculado). Só agendamentos "
        "ativos (`scheduled`, `confirmed`) podem ser movidos (`409 not_active`).\n\n"
        f"{CONFLICTS_DOC}"
    ),
    response_model=AppointmentOut,
    responses=error_responses(401, 403, 404, 409, 422),
    openapi_extra=DOC,
)
def move_appointment(
    appointment_id: uuid.UUID,
    payload: MoveAppointment,
    tenant: TenantDep,
    db: DbSession,
    user: AgendaManager,
) -> AppointmentOut:
    appointment = _get(db, appointment_id)
    if appointment.status not in ACTIVE_STATUSES:
        raise ApiError(409, "not_active", "Só agendamentos ativos podem ser movidos")
    offering = _offering(db, payload.offering_id or appointment.offering_id)
    provider_id = payload.provider_id or appointment.provider_id
    starts_at = payload.starts_at or appointment.starts_at
    ends_at = check_slot(
        db,
        tenant,
        provider_id=provider_id,
        offering=offering,
        starts_at=starts_at,
        allow_outside_hours=payload.allow_outside_hours,
        ignore=appointment.id,
    )
    appointment.provider_id = provider_id
    appointment.offering_id = offering.id
    appointment.starts_at = starts_at.astimezone(UTC)
    appointment.ends_at = ends_at
    flush_or_slot_taken(db)
    log.info(
        "appointment_moved",
        tenant_id=str(tenant.id),
        user_id=str(user.id),
        appointment_id=str(appointment.id),
    )
    return _out(appointment)


@router.post(
    "/{appointment_id}/status",
    summary="Confirmar, marcar atendido, falta ou cancelar",
    description=(
        "- `completed` (atendido) e `no_show` (faltou) só depois do horário de início "
        "(`409 too_early`).\n"
        "- `cancelled` libera o horário na hora.\n"
        "- Voltar um cancelado para `scheduled`/`confirmed` só se o horário ainda estiver livre "
        "(`409 slot_taken`)."
    ),
    response_model=AppointmentOut,
    responses=error_responses(401, 403, 404, 409, 422),
    openapi_extra=DOC,
)
def change_status(
    appointment_id: uuid.UUID,
    payload: StatusChange,
    tenant: TenantDep,
    db: DbSession,
    user: AgendaManager,
) -> AppointmentOut:
    appointment = _get(db, appointment_id)
    new = payload.status
    if new in ("completed", "no_show") and appointment.starts_at > datetime.now(UTC):
        raise ApiError(409, "too_early", "Ainda não chegou o horário")
    if new in ACTIVE_STATUSES and appointment.status not in ACTIVE_STATUSES:
        # reativar: o horário precisa continuar livre (encaixe permitido, sobreposição não)
        check_slot(
            db,
            tenant,
            provider_id=appointment.provider_id,
            offering=_offering(db, appointment.offering_id),
            starts_at=appointment.starts_at,
            allow_outside_hours=True,
            ignore=appointment.id,
        )
    appointment.status = new
    flush_or_slot_taken(db)
    log.info(
        "appointment_status_changed",
        tenant_id=str(tenant.id),
        user_id=str(user.id),
        appointment_id=str(appointment.id),
        status=new,
    )
    return _out(appointment)
