"""Regras para marcar e mudar agendamentos (usadas pela equipe e, no SAL-11, pela página pública).

Dupla reserva tem duas barreiras:
1. A linha do profissional é travada (`SELECT ... FOR UPDATE`) antes de conferir o horário:
   dois pedidos para o mesmo profissional ao mesmo tempo passam em fila, e o segundo já vê o
   primeiro.
2. A constraint de exclusão do banco (migração 0008) recusa qualquer sobreposição que escape.
Nos dois casos o resultado é `409 slot_taken`.
"""

import uuid
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.customers.models import Customer
from app.core.infra.errors import ApiError
from app.core.infra.tenancy import TenantContext
from app.core.scheduling.models import ACTIVE_STATUSES, Appointment, Offering, Provider, TimeOff

EXCLUSION_VIOLATION = "23P01"


def slot_taken() -> ApiError:
    return ApiError(409, "slot_taken", "Horário já ocupado")


def _lock_provider(db: Session, provider_id: uuid.UUID) -> Provider:
    provider = db.scalar(select(Provider).where(Provider.id == provider_id).with_for_update())
    if provider is None or not provider.is_active:
        raise ApiError(422, "unknown_provider", "Profissional não encontrado ou inativo")
    return provider


def _fits_working_hours(provider: Provider, starts: datetime, ends: datetime, tz: str) -> bool:
    """O horário inteiro cabe numa faixa da jornada (hora local). Jornadas não passam da
    meia-noite, então um horário que termina em outro dia nunca cabe."""
    local_start = starts.astimezone(ZoneInfo(tz))
    local_end = ends.astimezone(ZoneInfo(tz))
    if local_start.date() != local_end.date():
        return False
    return any(
        h.weekday == local_start.weekday()
        and h.start_time <= local_start.time()
        and local_end.time() <= h.end_time
        for h in provider.working_hours
    )


def _in_time_off(db: Session, provider_id: uuid.UUID, starts: datetime, ends: datetime) -> bool:
    return bool(
        db.scalar(
            select(TimeOff.id).where(
                (TimeOff.provider_id == provider_id) | (TimeOff.provider_id.is_(None)),
                TimeOff.starts_at < ends,
                TimeOff.ends_at > starts,
            )
        )
    )


def _overlaps(
    db: Session, provider_id: uuid.UUID, starts: datetime, ends: datetime, ignore: uuid.UUID | None
) -> bool:
    query = select(Appointment.id).where(
        Appointment.provider_id == provider_id,
        Appointment.status.in_(ACTIVE_STATUSES),
        Appointment.starts_at < ends,
        Appointment.ends_at > starts,
    )
    if ignore:
        query = query.where(Appointment.id != ignore)
    return bool(db.scalar(query))


def check_slot(
    db: Session,
    tenant: TenantContext,
    *,
    provider_id: uuid.UUID,
    offering: Offering,
    starts_at: datetime,
    allow_outside_hours: bool,
    ignore: uuid.UUID | None = None,
) -> datetime:
    """Confere tudo e devolve o fim do horário. Trava o profissional até o fim da transação."""
    if starts_at.tzinfo is None:
        raise ApiError(422, "validation_error", "Horário sem fuso")
    starts_at = starts_at.astimezone(UTC)
    if starts_at.second or starts_at.microsecond or starts_at.minute % 5:
        raise ApiError(422, "invalid_time_step", "Use horários de 5 em 5 minutos")
    provider = _lock_provider(db, provider_id)
    if offering.id not in {o.id for o in provider.offerings}:
        raise ApiError(422, "provider_cannot_do", "Esse profissional não faz esse serviço")
    ends_at = starts_at + timedelta(minutes=offering.duration_min)

    if _overlaps(db, provider_id, starts_at, ends_at, ignore):
        raise slot_taken()
    if not allow_outside_hours:
        if not _fits_working_hours(provider, starts_at, ends_at, tenant.timezone):
            raise ApiError(409, "outside_working_hours", "Fora da jornada do profissional")
        if _in_time_off(db, provider_id, starts_at, ends_at):
            raise ApiError(409, "provider_time_off", "Profissional de folga nesse horário")
    return ends_at


def require_service_consent(customer: Customer) -> None:
    if not any(c.purpose == "service" for c in customer.active_consents()):
        raise ApiError(
            409,
            "customer_without_consent",
            "O cliente não autorizou o uso dos dados para atendimento",
        )


def flush_or_slot_taken(db: Session) -> None:
    """Grava agora; se a constraint do banco recusar por sobreposição, responde slot_taken."""
    try:
        db.flush()
    except IntegrityError as exc:
        if getattr(exc.orig, "sqlstate", None) == EXCLUSION_VIOLATION:
            raise slot_taken() from None
        raise
