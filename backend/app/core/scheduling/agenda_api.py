"""Agenda (SAL-08): o dia ou a semana, por profissional.

- Quem tem `agenda.view_all` (dono, recepção) vê todos os profissionais.
- Quem só tem `agenda.view_own` (profissional) vê apenas o profissional ligado à própria conta,
  e o nome do cliente sem o telefone (só o necessário para atender).
"""

import uuid
from datetime import UTC, date, datetime, time, timedelta
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.accounts.auth import require_permission
from app.core.accounts.models import User
from app.core.accounts.permissions import Permission, permission_doc, permissions_for
from app.core.customers.models import Customer
from app.core.customers.phones import display_phone
from app.core.infra.errors import error_responses
from app.core.infra.tenancy import DbSession, TenantContext, TenantDep
from app.core.scheduling.models import Appointment, Offering, Provider, TimeOff
from app.core.scheduling.providers_api import Color, WorkingRange

router = APIRouter(prefix="/t/{slug}/agenda", tags=["Agenda"])

AgendaViewer = Annotated[User, require_permission(Permission.AGENDA_VIEW_OWN)]
Status = Literal["scheduled", "confirmed", "completed", "no_show", "cancelled"]
STATUS_DOC = (
    "`scheduled` (agendado), `confirmed` (confirmado), `completed` (atendido), `no_show` "
    "(faltou), `cancelled` (cancelado). Só `scheduled` e `confirmed` ocupam o horário."
)


class AgendaProvider(BaseModel):
    id: uuid.UUID
    name: str
    color: Color
    working_hours: list[WorkingRange]


class AgendaAppointment(BaseModel):
    id: uuid.UUID
    provider_id: uuid.UUID
    offering_id: uuid.UUID
    offering_name: str
    customer_id: uuid.UUID
    customer_name: str
    customer_phone_display: str | None = Field(
        description="Só para quem vê a agenda de todos; o profissional vê só o nome."
    )
    starts_at: datetime
    ends_at: datetime
    status: Status = Field(description=STATUS_DOC)
    source: Literal["staff", "public"] = Field(description="`public` = marcado pela página.")


class AgendaTimeOff(BaseModel):
    id: uuid.UUID
    provider_id: uuid.UUID | None = Field(description="`null` = vale para o estabelecimento.")
    starts_at: datetime
    ends_at: datetime
    reason: str | None


class AgendaOut(BaseModel):
    start_date: date
    days: int
    timezone: str = Field(description="Fuso para mostrar os horários (os instantes vêm em UTC).")
    scope: Literal["all", "own"] = Field(
        description="`all` = todos os profissionais; `own` = só o da conta de quem pediu."
    )
    own_provider_missing: bool = Field(
        description="`true` quando o escopo é `own` e a conta não está ligada a nenhum "
        "profissional (o dono precisa ligar em Profissionais)."
    )
    providers: list[AgendaProvider]
    appointments: list[AgendaAppointment]
    time_off: list[AgendaTimeOff]


def _window(start: date, days: int, tenant: TenantContext) -> tuple[datetime, datetime]:
    zone = ZoneInfo(tenant.timezone)
    begin = datetime.combine(start, time(0), tzinfo=zone).astimezone(UTC)
    end = datetime.combine(start + timedelta(days=days), time(0), tzinfo=zone).astimezone(UTC)
    return begin, end


@router.get(
    "",
    summary="Ver a agenda",
    description=(
        "Do dia `start` (data local) por `days` dias (1 = o dia; 7 = a semana). Traz os "
        "profissionais com a jornada, os agendamentos (inclusive cancelados e faltas, para a "
        "tela mostrar com outra cor) e as folgas que caem no período.\n\n"
        f"{STATUS_DOC}\n\n"
        "`provider_id` filtra um profissional (para quem vê todos)."
    ),
    response_model=AgendaOut,
    responses=error_responses(401, 403, 404, 422),
    openapi_extra=permission_doc(Permission.AGENDA_VIEW_OWN),
)
def get_agenda(
    tenant: TenantDep,
    db: DbSession,
    user: AgendaViewer,
    start: Annotated[date, Query(description="Primeiro dia, data local (AAAA-MM-DD).")],
    days: Annotated[int, Query(ge=1, le=7)] = 1,
    provider_id: Annotated[uuid.UUID | None, Query()] = None,
) -> AgendaOut:
    sees_all = Permission.AGENDA_VIEW_ALL in permissions_for(user.role)
    query = select(Provider).where(Provider.is_active).order_by(Provider.name)
    if not sees_all:
        query = query.where(Provider.user_id == user.id)
    elif provider_id:
        query = query.where(Provider.id == provider_id)
    providers = list(db.scalars(query))
    ids = [p.id for p in providers]

    begin, end = _window(start, days, tenant)
    appointments = (
        db.execute(
            select(Appointment, Offering.name, Customer.name, Customer.phone_e164)
            .join(Offering, Offering.id == Appointment.offering_id)
            .join(Customer, Customer.id == Appointment.customer_id)
            .where(
                Appointment.provider_id.in_(ids),
                Appointment.starts_at < end,
                Appointment.ends_at > begin,
            )
            .order_by(Appointment.starts_at)
        ).all()
        if ids
        else []
    )
    time_off = (
        db.scalars(
            select(TimeOff)
            .where(
                (TimeOff.provider_id.in_(ids)) | (TimeOff.provider_id.is_(None)),
                TimeOff.starts_at < end,
                TimeOff.ends_at > begin,
            )
            .order_by(TimeOff.starts_at)
        ).all()
        if ids
        else []
    )

    return AgendaOut(
        start_date=start,
        days=days,
        timezone=tenant.timezone,
        scope="all" if sees_all else "own",
        own_provider_missing=not sees_all and not providers,
        providers=[
            AgendaProvider(
                id=p.id,
                name=p.name,
                color=p.color,
                working_hours=[
                    WorkingRange(
                        weekday=h.weekday,
                        start=h.start_time.strftime("%H:%M"),
                        end=h.end_time.strftime("%H:%M"),
                    )
                    for h in p.working_hours
                ],
            )
            for p in providers
        ],
        appointments=[
            AgendaAppointment(
                id=a.id,
                provider_id=a.provider_id,
                offering_id=a.offering_id,
                offering_name=offering_name,
                customer_id=a.customer_id,
                customer_name=customer_name,
                customer_phone_display=display_phone(phone) if sees_all else None,
                starts_at=a.starts_at,
                ends_at=a.ends_at,
                status=a.status,
                source=a.source,
            )
            for a, offering_name, customer_name, phone in appointments
        ],
        time_off=[
            AgendaTimeOff(
                id=t.id,
                provider_id=t.provider_id,
                starts_at=t.starts_at,
                ends_at=t.ends_at,
                reason=t.reason,
            )
            for t in time_off
        ],
    )
