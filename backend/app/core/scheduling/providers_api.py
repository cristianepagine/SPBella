"""Profissionais (SAL-06): jornada semanal, itens que realizam e folgas."""

import uuid
from datetime import UTC, date, datetime, time, timedelta
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Response
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.accounts.auth import require_permission
from app.core.accounts.models import User
from app.core.accounts.permissions import Permission, permission_doc
from app.core.infra.errors import ApiError, FieldError, error_responses
from app.core.infra.tenancy import DbSession, TenantContext, TenantDep
from app.core.scheduling.models import (
    PROVIDER_COLORS,
    Offering,
    Provider,
    TimeOff,
    WorkingHours,
)

router = APIRouter(prefix="/t/{slug}/providers", tags=["Agenda"])

TeamViewer = Annotated[User, require_permission(Permission.AGENDA_VIEW_OWN)]
ProviderManager = Annotated[User, require_permission(Permission.PROVIDERS_MANAGE)]
VIEW_DOC = permission_doc(Permission.AGENDA_VIEW_OWN)
MANAGE_DOC = permission_doc(Permission.PROVIDERS_MANAGE)

Color = Literal[PROVIDER_COLORS]  # type: ignore[valid-type]
TIME_PATTERN = r"^([01]\d|2[0-3]):[0-5]\d$"
WEEKDAY_DOC = "0 = segunda, 1 = terça, ..., 5 = sábado, 6 = domingo."


# --- esquemas ----------------------------------------------------------------------------


class WorkingRange(BaseModel):
    weekday: int = Field(ge=0, le=6, description=WEEKDAY_DOC)
    start: str = Field(pattern=TIME_PATTERN, description="Hora local, `HH:MM`.", examples=["09:00"])
    end: str = Field(pattern=TIME_PATTERN, description="Hora local, `HH:MM`.", examples=["12:00"])


class ProviderOut(BaseModel):
    id: uuid.UUID
    name: str
    color: Color = Field(description="Cor na agenda.")
    is_active: bool
    user_id: uuid.UUID | None = Field(description="Conta de acesso ligada (se a pessoa entra).")
    offering_ids: list[uuid.UUID] = Field(description="Itens (serviços) que realiza.")
    working_hours: list[WorkingRange] = Field(
        description="Jornada semanal. Dia sem faixa = não trabalha. Duas faixas no mesmo dia = "
        "intervalo entre elas (ex.: almoço)."
    )


class NewProvider(BaseModel):
    name: str = Field(min_length=1, max_length=120, examples=["Paula Souza"])
    color: Color | None = Field(default=None, description="Sem cor: o sistema escolhe uma livre.")
    user_id: uuid.UUID | None = None
    offering_ids: list[uuid.UUID] = Field(default_factory=list)
    working_hours: list[WorkingRange] = Field(default_factory=list)


class ProviderChanges(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    color: Color | None = None
    is_active: bool | None = None
    user_id: uuid.UUID | None = Field(default=None, description="`null` desliga a conta.")


class WorkingHoursIn(BaseModel):
    ranges: list[WorkingRange]


class OfferingsIn(BaseModel):
    offering_ids: list[uuid.UUID]


class TimeOffOut(BaseModel):
    id: uuid.UUID
    start_date: date = Field(description="Primeiro dia de folga (data local).")
    end_date: date = Field(description="Último dia de folga (data local, inclusive).")
    reason: str | None
    starts_at: datetime = Field(description="Início em UTC (meia-noite local do primeiro dia).")
    ends_at: datetime = Field(
        description="Fim em UTC (meia-noite local do dia seguinte ao último)."
    )


class NewTimeOff(BaseModel):
    start_date: date = Field(examples=["2026-12-24"])
    end_date: date = Field(examples=["2026-12-26"])
    reason: str | None = Field(default=None, max_length=120, examples=["Férias"])


# --- utilitários -------------------------------------------------------------------------


def _field_error(field: str, code: str) -> ApiError:
    return ApiError(
        422, "validation_error", "Dados inválidos", fields=[FieldError(field=field, code=code)]
    )


def _parse_time(value: str) -> time:
    hours, minutes = map(int, value.split(":"))
    return time(hours, minutes)


def _validate_ranges(ranges: list[WorkingRange]) -> list[tuple[int, time, time]]:
    parsed = []
    for r in ranges:
        start, end = _parse_time(r.start), _parse_time(r.end)
        if start.minute % 5 or end.minute % 5:
            raise _field_error("working_hours", "invalid_time_step")
        if start >= end:
            raise _field_error("working_hours", "start_after_end")
        parsed.append((r.weekday, start, end))
    parsed.sort()
    for (day_a, _, end_a), (day_b, start_b, _) in zip(parsed, parsed[1:], strict=False):
        if day_a == day_b and start_b < end_a:
            raise _field_error("working_hours", "overlapping_hours")
    return parsed


def _set_hours(provider: Provider, ranges: list[WorkingRange]) -> None:
    provider.working_hours = [
        WorkingHours(weekday=day, start_time=start, end_time=end)
        for day, start, end in _validate_ranges(ranges)
    ]


def _set_offerings(db: DbSession, provider: Provider, ids: list[uuid.UUID]) -> None:
    unique = set(ids)
    offerings = list(db.scalars(select(Offering).where(Offering.id.in_(unique)))) if unique else []
    if len(offerings) != len(unique):
        raise _field_error("offering_ids", "unknown_offering")
    provider.offerings = offerings


def _set_user(db: DbSession, provider: Provider, user_id: uuid.UUID | None) -> None:
    if user_id is None:
        provider.user_id = None
        return
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise _field_error("user_id", "unknown_user")
    taken = db.scalar(select(Provider.id).where(Provider.user_id == user_id))
    if taken and taken != provider.id:
        raise ApiError(409, "user_already_linked", "Essa conta já está ligada a outro profissional")
    provider.user_id = user_id


def _free_color(db: DbSession) -> str:
    used = set(db.scalars(select(Provider.color).where(Provider.is_active)))
    return next((c for c in PROVIDER_COLORS if c not in used), PROVIDER_COLORS[0])


def _out(provider: Provider) -> ProviderOut:
    return ProviderOut(
        id=provider.id,
        name=provider.name,
        color=provider.color,
        is_active=provider.is_active,
        user_id=provider.user_id,
        offering_ids=[o.id for o in provider.offerings],
        working_hours=[
            WorkingRange(
                weekday=h.weekday,
                start=h.start_time.strftime("%H:%M"),
                end=h.end_time.strftime("%H:%M"),
            )
            for h in provider.working_hours
        ],
    )


def _get(db: DbSession, provider_id: uuid.UUID) -> Provider:
    provider = db.get(Provider, provider_id)
    if provider is None:
        raise ApiError(404, "not_found", "Profissional não encontrado")
    return provider


def _local_midnight_utc(day: date, tenant: TenantContext) -> datetime:
    return datetime.combine(day, time(0), tzinfo=ZoneInfo(tenant.timezone)).astimezone(UTC)


def _time_off_out(item: TimeOff, tenant: TenantContext) -> TimeOffOut:
    zone = ZoneInfo(tenant.timezone)
    return TimeOffOut(
        id=item.id,
        start_date=item.starts_at.astimezone(zone).date(),
        end_date=(item.ends_at.astimezone(zone) - timedelta(seconds=1)).date(),
        reason=item.reason,
        starts_at=item.starts_at,
        ends_at=item.ends_at,
    )


# --- profissionais -----------------------------------------------------------------------


@router.get(
    "",
    summary="Listar profissionais",
    description="Em ordem alfabética, com jornada e itens que realizam. Por padrão só os ativos.",
    response_model=list[ProviderOut],
    responses=error_responses(401, 403, 404),
    openapi_extra=VIEW_DOC,
)
def list_providers(
    db: DbSession, _user: TeamViewer, include_inactive: bool = False
) -> list[ProviderOut]:
    query = select(Provider).order_by(Provider.name)
    if not include_inactive:
        query = query.where(Provider.is_active)
    return [_out(p) for p in db.scalars(query)]


@router.post(
    "",
    summary="Cadastrar profissional",
    description=(
        "Com jornada semanal e itens que realiza (os dois podem vir depois).\n\n"
        "- `422` com `fields[0].code`: `start_after_end`, `overlapping_hours`, "
        "`invalid_time_step` (minutos em múltiplos de 5), `unknown_offering`, `unknown_user`.\n"
        "- `409 user_already_linked`: a conta já está ligada a outro profissional."
    ),
    status_code=201,
    response_model=ProviderOut,
    responses=error_responses(401, 403, 404, 409, 422),
    openapi_extra=MANAGE_DOC,
)
def create_provider(payload: NewProvider, db: DbSession, _user: ProviderManager) -> ProviderOut:
    name = payload.name.strip()
    if not name:
        raise _field_error("name", "string_too_short")
    provider = Provider(id=uuid.uuid4(), name=name, color=payload.color or _free_color(db))
    _set_hours(provider, payload.working_hours)
    _set_offerings(db, provider, payload.offering_ids)
    _set_user(db, provider, payload.user_id)
    db.add(provider)
    db.flush()
    return _out(provider)


@router.patch(
    "/{provider_id}",
    summary="Alterar profissional",
    description="Nome, cor, ativo e conta ligada. Só os campos enviados mudam.",
    response_model=ProviderOut,
    responses=error_responses(401, 403, 404, 409, 422),
    openapi_extra=MANAGE_DOC,
)
def change_provider(
    provider_id: uuid.UUID, payload: ProviderChanges, db: DbSession, _user: ProviderManager
) -> ProviderOut:
    provider = _get(db, provider_id)
    if payload.name is not None:
        if not payload.name.strip():
            raise _field_error("name", "string_too_short")
        provider.name = payload.name.strip()
    if payload.color is not None:
        provider.color = payload.color
    if payload.is_active is not None:
        provider.is_active = payload.is_active
    if "user_id" in payload.model_fields_set:
        _set_user(db, provider, payload.user_id)
    db.flush()
    return _out(provider)


@router.put(
    "/{provider_id}/working-hours",
    summary="Definir a jornada semanal",
    description=(
        f"Substitui a semana inteira pelas faixas enviadas. {WEEKDAY_DOC} Horas locais "
        "`HH:MM`, em múltiplos de 5 minutos. Faixas do mesmo dia não podem se sobrepor. "
        "Lista vazia = o profissional não tem horários."
    ),
    response_model=ProviderOut,
    responses=error_responses(401, 403, 404, 422),
    openapi_extra=MANAGE_DOC,
)
def set_working_hours(
    provider_id: uuid.UUID, payload: WorkingHoursIn, db: DbSession, _user: ProviderManager
) -> ProviderOut:
    provider = _get(db, provider_id)
    _set_hours(provider, payload.ranges)
    db.flush()
    return _out(provider)


@router.put(
    "/{provider_id}/offerings",
    summary="Definir o que o profissional realiza",
    description="Substitui a lista inteira. `422 unknown_offering` se algum ID não existir.",
    response_model=ProviderOut,
    responses=error_responses(401, 403, 404, 422),
    openapi_extra=MANAGE_DOC,
)
def set_offerings(
    provider_id: uuid.UUID, payload: OfferingsIn, db: DbSession, _user: ProviderManager
) -> ProviderOut:
    provider = _get(db, provider_id)
    _set_offerings(db, provider, payload.offering_ids)
    db.flush()
    return _out(provider)


# --- folgas ------------------------------------------------------------------------------


@router.get(
    "/{provider_id}/time-off",
    summary="Listar folgas",
    description="Folgas e férias que ainda não terminaram, da mais próxima para a mais distante.",
    response_model=list[TimeOffOut],
    responses=error_responses(401, 403, 404),
    openapi_extra=VIEW_DOC,
)
def list_time_off(
    provider_id: uuid.UUID, tenant: TenantDep, db: DbSession, _user: TeamViewer
) -> list[TimeOffOut]:
    _get(db, provider_id)
    items = db.scalars(
        select(TimeOff)
        .where(TimeOff.provider_id == provider_id, TimeOff.ends_at > datetime.now(UTC))
        .order_by(TimeOff.starts_at)
    )
    return [_time_off_out(i, tenant) for i in items]


@router.post(
    "/{provider_id}/time-off",
    summary="Registrar folga ou férias",
    description=(
        "Dias inteiros, do `start_date` ao `end_date` (inclusive), no fuso do estabelecimento. "
        "Nesses dias o profissional não aparece com horários livres. "
        "`422 end_before_start` se o fim vier antes do início; no máximo 366 dias."
    ),
    status_code=201,
    response_model=TimeOffOut,
    responses=error_responses(401, 403, 404, 422),
    openapi_extra=MANAGE_DOC,
)
def add_time_off(
    provider_id: uuid.UUID,
    payload: NewTimeOff,
    tenant: TenantDep,
    db: DbSession,
    _user: ProviderManager,
) -> TimeOffOut:
    _get(db, provider_id)
    if payload.end_date < payload.start_date:
        raise _field_error("end_date", "end_before_start")
    if (payload.end_date - payload.start_date).days > 365:
        raise _field_error("end_date", "too_long")
    item = TimeOff(
        id=uuid.uuid4(),
        provider_id=provider_id,
        starts_at=_local_midnight_utc(payload.start_date, tenant),
        ends_at=_local_midnight_utc(payload.end_date + timedelta(days=1), tenant),
        reason=(payload.reason or "").strip() or None,
    )
    db.add(item)
    db.flush()
    return _time_off_out(item, tenant)


@router.delete(
    "/{provider_id}/time-off/{time_off_id}",
    summary="Cancelar folga",
    description="Remove a folga; os dias voltam a seguir a jornada semanal.",
    status_code=204,
    responses=error_responses(401, 403, 404),
    openapi_extra=MANAGE_DOC,
)
def delete_time_off(
    provider_id: uuid.UUID, time_off_id: uuid.UUID, db: DbSession, _user: ProviderManager
) -> Response:
    item = db.get(TimeOff, time_off_id)
    if item is None or item.provider_id != provider_id:
        raise ApiError(404, "not_found", "Folga não encontrada")
    db.delete(item)
    return Response(status_code=204)
