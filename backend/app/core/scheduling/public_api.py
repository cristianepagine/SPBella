"""Agendamento online (SAL-11): a página pública do estabelecimento, sem login.

O cliente final escolhe o serviço, o profissional (ou "sem preferência"), o dia e a hora, e
informa nome, telefone e consentimento. Não cria conta.

Proteções:
- Turnstile e limite por IP e por telefone ao marcar; limite por IP ao consultar horários.
- Só se marca um horário que esteja em `free_slots` (mesmo cálculo da equipe), respeitando a
  antecedência mínima e até quantos dias à frente (Configurações). Depois o `check_slot` trava o
  profissional e confere de novo, então dois clientes no mesmo horário: só um consegue.
- A resposta é a mesma para telefone novo ou já cadastrado (não revela quem é cliente).
"""

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.core.audit.service import record
from app.core.customers.models import Consent, Customer
from app.core.customers.phones import InvalidPhoneError, normalize_phone
from app.core.customers.search import normalize_text
from app.core.infra.errors import ApiError, FieldError, error_responses
from app.core.infra.logging import log
from app.core.infra.ratelimit import client_ip
from app.core.infra.security import is_valid_email, normalize_email
from app.core.infra.tenancy import DbSession, TenantContext, TenantDep
from app.core.scheduling.availability import free_slots, schedule_settings
from app.core.scheduling.availability_api import AvailabilityOut, FreeSlot
from app.core.scheduling.booking import check_slot, flush_or_slot_taken
from app.core.scheduling.models import (
    ACTIVE_STATUSES,
    Appointment,
    Offering,
    Provider,
    ScheduleSettings,
)

router = APIRouter(prefix="/t/{slug}/booking", tags=["Agendamento online"])

# Limites (por processo; o WAF do Cloudflare é a primeira barreira).
AVAILABILITY_LIMIT = (120, 10 * 60)  # por IP
BOOKING_IP_LIMIT = (10, 60 * 60)
BOOKING_PHONE_LIMIT = (5, 60 * 60)


class PublicOffering(BaseModel):
    id: uuid.UUID
    name: str = Field(examples=["Corte feminino"])
    duration_min: int
    extras: dict[str, int | str] = Field(
        default_factory=dict,
        description="Dados da vertical. No salão: `price_minor` (menor unidade da moeda).",
        examples=[{"price_minor": 8000}],
    )


class PublicProvider(BaseModel):
    id: uuid.UUID
    name: str = Field(description="Como aparece na página.", examples=["Paula"])
    color: str
    offering_ids: list[uuid.UUID]


class Catalog(BaseModel):
    offerings: list[PublicOffering] = Field(
        description="Ativos e feitos por pelo menos um profissional ativo."
    )
    providers: list[PublicProvider]
    min_notice_min: int = Field(description="Antecedência mínima para marcar, em minutos.")
    max_days_ahead: int = Field(description="Até quantos dias à frente dá para marcar.")
    privacy_policy_version: str


Purpose = Literal["service", "reminders", "marketing"]


class PublicBooking(BaseModel):
    offering_id: uuid.UUID
    provider_id: uuid.UUID | None = Field(
        default=None, description='Vazio = "sem preferência": o sistema escolhe quem está livre.'
    )
    starts_at: datetime = Field(description="Um dos horários de `/booking/availability`.")
    name: str = Field(min_length=1, max_length=120)
    phone: str = Field(min_length=1, max_length=32)
    email: str | None = Field(default=None, max_length=254)
    locale: Literal["pt-BR", "es"] | None = Field(
        default=None, description="Idioma em que o cliente usou a página."
    )
    consents: list[Purpose] = Field(
        description="Precisa incluir `service` (usar os dados para o atendimento). "
        "`reminders` e `marketing` são opcionais."
    )
    turnstile_token: str | None = None


class BookingConfirmation(BaseModel):
    appointment_id: uuid.UUID
    offering_name: str
    provider_name: str
    starts_at: datetime
    ends_at: datetime


# --- utilitários -------------------------------------------------------------------------


def _field_error(field: str, code: str) -> ApiError:
    return ApiError(
        422, "validation_error", "Dados inválidos", fields=[FieldError(field=field, code=code)]
    )


def _ip(request: Request) -> str:
    return client_ip(request, request.app.state.settings)


def _limit(request: Request, key: str, rule: tuple[int, int]) -> None:
    request.app.state.rate_limiter.hit(key, *rule)


def _bookable_providers(db: DbSession) -> list[Provider]:
    return list(db.scalars(select(Provider).where(Provider.is_active).order_by(Provider.name)))


def _offering(db: DbSession, offering_id: uuid.UUID) -> Offering:
    offering = db.get(Offering, offering_id)
    if offering is None or not offering.is_active:
        raise ApiError(422, "unknown_offering", "Serviço não encontrado ou desativado")
    return offering


def _window(tenant: TenantContext, rules: ScheduleSettings) -> tuple[datetime, date]:
    """Primeiro instante que dá para marcar e último dia (local) aberto."""
    now = datetime.now(UTC)
    today = now.astimezone(ZoneInfo(tenant.timezone)).date()
    return now + timedelta(minutes=rules.min_notice_min), today + timedelta(
        days=rules.max_days_ahead
    )


# --- rotas -------------------------------------------------------------------------------


@router.get(
    "/catalog",
    summary="Serviços e profissionais da página",
    description=(
        "O que o cliente pode escolher, sem dados pessoais: serviços ativos (com o preço, no "
        "salão), profissionais ativos (só o nome de exibição e a cor) e as regras de antecedência."
    ),
    response_model=Catalog,
    responses=error_responses(404),
)
def get_catalog(request: Request, db: DbSession) -> Catalog:
    providers = _bookable_providers(db)
    offered = {o.id for p in providers for o in p.offerings if o.is_active}
    offerings = [
        o
        for o in db.scalars(select(Offering).where(Offering.is_active).order_by(Offering.name))
        if o.id in offered
    ]
    hook = request.app.state.vertical.public_offering_extras
    extras = hook(db, [o.id for o in offerings]) if hook else {}
    rules = schedule_settings(db)
    return Catalog(
        offerings=[
            PublicOffering(
                id=o.id, name=o.name, duration_min=o.duration_min, extras=extras.get(o.id, {})
            )
            for o in offerings
        ],
        providers=[
            PublicProvider(
                id=p.id,
                name=p.name,
                color=p.color,
                offering_ids=[o.id for o in p.offerings if o.is_active],
            )
            for p in providers
        ],
        min_notice_min=rules.min_notice_min,
        max_days_ahead=rules.max_days_ahead,
        privacy_policy_version=request.app.state.settings.privacy_policy_version,
    )


@router.get(
    "/availability",
    summary="Horários livres (página pública)",
    description=(
        "O mesmo cálculo da equipe (jornada − bloqueios − agendamentos, duração e intervalo "
        "mínimo), já sem os horários antes da antecedência mínima e sem os dias além do limite "
        "(dia fora da janela: lista vazia). Limite: 120 consultas por IP a cada 10 min."
    ),
    response_model=AvailabilityOut,
    responses=error_responses(404, 422, 429),
)
def get_public_availability(
    request: Request,
    tenant: TenantDep,
    db: DbSession,
    offering_id: Annotated[uuid.UUID, Query()],
    day: Annotated[date, Query(alias="date", description="Data local (AAAA-MM-DD).")],
    provider_id: Annotated[uuid.UUID | None, Query()] = None,
) -> AvailabilityOut:
    _limit(request, f"booking-availability:{tenant.id}:{_ip(request)}", AVAILABILITY_LIMIT)
    offering = _offering(db, offering_id)
    not_before, last_day = _window(tenant, schedule_settings(db))
    slots = []
    if day <= last_day:
        slots = free_slots(
            db,
            tenant,
            offering=offering,
            day=day,
            provider_ids=[provider_id] if provider_id else None,
            not_before=not_before,
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


@router.post(
    "",
    summary="Marcar pela página pública",
    description=(
        "Marca o horário sem criar conta. Se o telefone já é de um cliente, o agendamento vai "
        "para ele (nome e e-mail cadastrados não mudam); senão, cadastra. Registra os "
        "consentimentos com a versão da política de privacidade (origem `public_booking`) e "
        "fica no log de auditoria.\n\n"
        "- Exige `turnstile_token` (`400 turnstile_failed`). Limites: 10 por IP e 5 por "
        "telefone a cada hora (`429`).\n"
        '- Sem `provider_id` ("sem preferência"): vai para o profissional livre com menos '
        "atendimentos no dia.\n"
        "- `409 slot_unavailable`: o horário não está (mais) livre — outra pessoa marcou, "
        "passou da antecedência mínima ou está além do limite de dias. Mostre os horários de "
        "novo.\n"
        "- `422` com `fields[0].code`: `invalid_phone`, `invalid_email`, `consent_required`, "
        "`string_too_short`; ou `422 unknown_offering`."
    ),
    status_code=201,
    response_model=BookingConfirmation,
    responses=error_responses(400, 404, 409, 422, 429),
)
def create_public_booking(
    payload: PublicBooking, request: Request, tenant: TenantDep, db: DbSession
) -> BookingConfirmation:
    _limit(request, f"booking:{tenant.id}:{_ip(request)}", BOOKING_IP_LIMIT)
    if not request.app.state.turnstile.verify(payload.turnstile_token, _ip(request)):
        raise ApiError(400, "turnstile_failed", "Verificação anti-robô falhou")
    name = payload.name.strip()
    if not name:
        raise _field_error("name", "string_too_short")
    try:
        phone = normalize_phone(payload.phone, tenant.country)
    except InvalidPhoneError:
        raise _field_error("phone", "invalid_phone") from None
    email = None
    if payload.email and payload.email.strip():
        email = normalize_email(payload.email)
        if not is_valid_email(email):
            raise _field_error("email", "invalid_email")
    if "service" not in payload.consents:
        raise _field_error("consents", "consent_required")
    _limit(request, f"booking-phone:{tenant.id}:{phone}", BOOKING_PHONE_LIMIT)

    offering = _offering(db, payload.offering_id)
    starts_at = payload.starts_at.astimezone(UTC) if payload.starts_at.tzinfo else None
    if starts_at is None:
        raise ApiError(422, "validation_error", "Horário sem fuso")
    not_before, last_day = _window(tenant, schedule_settings(db))
    day = starts_at.astimezone(ZoneInfo(tenant.timezone)).date()
    free = []
    if day <= last_day:
        free = [
            s.provider_id
            for s in free_slots(
                db,
                tenant,
                offering=offering,
                day=day,
                provider_ids=[payload.provider_id] if payload.provider_id else None,
                not_before=not_before,
            )
            if s.starts_at == starts_at
        ]
    if not free:
        raise _unavailable()
    provider_id = _least_busy(db, free, tenant, day)
    try:
        ends_at = check_slot(
            db,
            tenant,
            provider_id=provider_id,
            offering=offering,
            starts_at=starts_at,
            allow_outside_hours=False,
        )
    except ApiError as exc:
        # Alguém marcou no meio do caminho: para o cliente, é só "esse horário não está livre".
        if exc.status_code == 409:
            raise _unavailable() from None
        raise

    customer, created = _customer(db, name=name, phone=phone, email=email, locale=payload.locale)
    _grant_consents(
        db, request, customer, payload.consents, request.app.state.settings.privacy_policy_version
    )
    if created:
        record(
            db,
            request,
            action="customer.created",
            entity_type="customer",
            entity_id=customer.id,
            actor=None,
            actor_type="customer",
            fields=[f for f in ("name", "phone", "email", "locale") if getattr(payload, f)],
        )
    appointment = Appointment(
        id=uuid.uuid4(),
        provider_id=provider_id,
        offering_id=offering.id,
        customer_id=customer.id,
        starts_at=starts_at,
        ends_at=ends_at,
        status="scheduled",
        source="public",
        created_by=None,
    )
    db.add(appointment)
    try:
        flush_or_slot_taken(db)
    except ApiError:
        raise _unavailable() from None
    log.info(
        "public_booking_created",
        tenant_id=str(tenant.id),
        appointment_id=str(appointment.id),
        new_customer=created,
    )
    provider = db.get(Provider, provider_id)
    return BookingConfirmation(
        appointment_id=appointment.id,
        offering_name=offering.name,
        provider_name=provider.name,
        starts_at=starts_at,
        ends_at=ends_at,
    )


def _unavailable() -> ApiError:
    return ApiError(409, "slot_unavailable", "Esse horário não está mais livre")


def _least_busy(
    db: DbSession, candidates: list[uuid.UUID], tenant: TenantContext, day: date
) -> uuid.UUID:
    if len(candidates) == 1:
        return candidates[0]
    zone = ZoneInfo(tenant.timezone)
    begin = datetime.combine(day, datetime.min.time(), tzinfo=zone)
    end = begin + timedelta(days=1)
    load = dict(
        db.execute(
            select(Appointment.provider_id, func.count())
            .where(
                Appointment.provider_id.in_(candidates),
                Appointment.status.in_(ACTIVE_STATUSES),
                Appointment.starts_at >= begin,
                Appointment.starts_at < end,
            )
            .group_by(Appointment.provider_id)
        ).all()
    )
    return min(candidates, key=lambda p: (load.get(p, 0), str(p)))


def _customer(
    db: DbSession, *, name: str, phone: str, email: str | None, locale: str | None
) -> tuple[Customer, bool]:
    existing = db.scalar(
        select(Customer).where(Customer.phone_e164 == phone).order_by(Customer.created_at).limit(1)
    )
    if existing is not None:
        return existing, False
    customer = Customer(
        id=uuid.uuid4(),
        name=name,
        search_name=normalize_text(name),
        phone_e164=phone,
        email=email,
        locale=locale,
    )
    db.add(customer)
    db.flush()
    return customer, True


def _grant_consents(
    db: DbSession, request: Request, customer: Customer, purposes: list[str], policy: str
) -> None:
    active = {c.purpose for c in customer.active_consents()}
    new = sorted(set(purposes) - active)
    for purpose in new:
        db.add(
            Consent(
                customer=customer,
                purpose=purpose,
                policy_version=policy,
                source="public_booking",
                recorded_by=None,
            )
        )
    if new:
        record(
            db,
            request,
            action="consent.granted",
            entity_type="customer",
            entity_id=customer.id,
            actor=None,
            actor_type="customer",
            fields=new,
        )
