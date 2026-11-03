"""Horários livres = jornada − bloqueios − agendamentos ativos, respeitando a duração do serviço e
o intervalo mínimo entre atendimentos.

Usado pela equipe (sugestões no "Novo agendamento") e, no SAL-11, pela página pública.

- A jornada é em hora local; cada faixa vira instantes UTC com o fuso do estabelecimento, então
  dias com horário de verão funcionam (a faixa tem a duração real daquele dia).
- O serviço precisa caber inteiro numa faixa: não atravessa o almoço nem a meia-noite.
- O intervalo mínimo (buffer) vale antes e depois de cada agendamento ativo.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.infra.tenancy import TenantContext
from app.core.scheduling.models import (
    ACTIVE_STATUSES,
    Appointment,
    Offering,
    Provider,
    ScheduleSettings,
    TimeOff,
)


@dataclass(frozen=True)
class Slot:
    provider_id: uuid.UUID
    starts_at: datetime  # UTC
    ends_at: datetime  # UTC


def schedule_settings(db: Session) -> ScheduleSettings:
    return db.get(ScheduleSettings, 1) or ScheduleSettings(id=1, buffer_min=0, slot_step_min=15)


def free_slots(
    db: Session,
    tenant: TenantContext,
    *,
    offering: Offering,
    day: date,
    provider_ids: list[uuid.UUID] | None = None,
    not_before: datetime | None = None,
) -> list[Slot]:
    """Horários livres do dia (data local) para o serviço, por profissional que o realiza."""
    settings = schedule_settings(db)
    zone = ZoneInfo(tenant.timezone)
    duration = timedelta(minutes=offering.duration_min)
    buffer = timedelta(minutes=settings.buffer_min)
    step = timedelta(minutes=settings.slot_step_min)
    day_begin = datetime.combine(day, time(0), tzinfo=zone).astimezone(UTC)
    day_end = datetime.combine(day + timedelta(days=1), time(0), tzinfo=zone).astimezone(UTC)

    query = select(Provider).where(Provider.is_active).order_by(Provider.name)
    if provider_ids is not None:
        query = query.where(Provider.id.in_(provider_ids))
    providers = [p for p in db.scalars(query) if offering.id in {o.id for o in p.offerings}]
    if not providers:
        return []
    ids = [p.id for p in providers]

    # Ocupado: agendamentos ativos (com o intervalo mínimo dos dois lados) e bloqueios.
    margin = buffer + duration
    busy: dict[uuid.UUID | None, list[tuple[datetime, datetime]]] = {}
    for a in db.scalars(
        select(Appointment).where(
            Appointment.provider_id.in_(ids),
            Appointment.status.in_(ACTIVE_STATUSES),
            Appointment.starts_at < day_end + margin,
            Appointment.ends_at > day_begin - margin,
        )
    ):
        busy.setdefault(a.provider_id, []).append((a.starts_at - buffer, a.ends_at + buffer))
    for t in db.scalars(
        select(TimeOff).where(
            TimeOff.provider_id.in_(ids) | TimeOff.provider_id.is_(None),
            TimeOff.starts_at < day_end,
            TimeOff.ends_at > day_begin,
        )
    ):
        busy.setdefault(t.provider_id, []).append((t.starts_at, t.ends_at))
    salon_wide = busy.get(None, [])

    slots: list[Slot] = []
    weekday = day.weekday()  # 0 = segunda, igual à jornada
    for provider in providers:
        blocked = busy.get(provider.id, []) + salon_wide
        for hours in provider.working_hours:
            if hours.weekday != weekday:
                continue
            start = datetime.combine(day, hours.start_time, tzinfo=zone).astimezone(UTC)
            end = datetime.combine(day, hours.end_time, tzinfo=zone).astimezone(UTC)
            candidate = start
            while candidate + duration <= end:
                finish = candidate + duration
                too_soon = not_before is not None and candidate < not_before
                if not too_soon and not any(b0 < finish and b1 > candidate for b0, b1 in blocked):
                    slots.append(Slot(provider.id, candidate, finish))
                candidate += step
    slots.sort(key=lambda s: (s.starts_at, str(s.provider_id)))
    return slots
