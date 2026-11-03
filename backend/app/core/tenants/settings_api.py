"""Configurações do estabelecimento (SAL-03): nome, idioma padrão e fuso. Só o dono."""

from typing import Annotated, Literal
from zoneinfo import available_timezones

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from app.core.accounts.auth import require_permission
from app.core.accounts.models import User
from app.core.accounts.permissions import Permission, permission_doc
from app.core.customers.phones import InvalidPhoneError, normalize_phone
from app.core.infra.errors import ApiError, FieldError, error_responses
from app.core.infra.logging import log
from app.core.infra.tenancy import (
    DbSession,
    TenantContext,
    TenantDep,
    load_tenant,
    update_tenant_profile,
)
from app.core.scheduling.availability import schedule_settings
from app.core.scheduling.models import ScheduleSettings

router = APIRouter(prefix="/t/{slug}/settings", tags=["Configurações"])

SettingsManager = Annotated[User, require_permission(Permission.SETTINGS_MANAGE)]

# Fusos sugeridos por país (a API aceita qualquer fuso IANA válido).
COUNTRY_TIMEZONES = {
    "BR": [
        "America/Sao_Paulo",
        "America/Bahia",
        "America/Fortaleza",
        "America/Recife",
        "America/Maceio",
        "America/Belem",
        "America/Araguaina",
        "America/Santarem",
        "America/Manaus",
        "America/Cuiaba",
        "America/Campo_Grande",
        "America/Porto_Velho",
        "America/Boa_Vista",
        "America/Rio_Branco",
        "America/Noronha",
    ],
    "PY": ["America/Asuncion"],
}


SlotStep = Literal[5, 10, 15, 20, 30, 60]


class TenantSettings(BaseModel):
    name: str = Field(examples=["Studio Bella"])
    locale: Literal["pt-BR", "es"] = Field(
        description="Idioma padrão: o da página pública e o de quem ainda não escolheu um."
    )
    timezone: str = Field(description="Fuso IANA da agenda.", examples=["America/Sao_Paulo"])
    currency: Literal["BRL", "PYG"] = Field(
        description="Somente leitura. Definida na criação: mudar a moeda mudaria o valor de "
        "todos os preços já cadastrados."
    )
    country: Literal["BR", "PY"]
    timezone_options: list[str] = Field(description="Fusos sugeridos para o país.")
    buffer_min: int = Field(
        description="Intervalo mínimo entre um atendimento e o próximo do mesmo profissional, "
        "em minutos (0 a 120, de 5 em 5)."
    )
    slot_step_min: SlotStep = Field(
        description="De quantos em quantos minutos os horários livres são oferecidos."
    )
    min_notice_min: int = Field(
        description="Página pública: antecedência mínima para marcar, em minutos (0 a 10080)."
    )
    max_days_ahead: int = Field(
        description="Página pública: até quantos dias à frente dá para marcar (1 a 365)."
    )
    whatsapp_phone: str | None = Field(
        description="Página pública: número do botão de WhatsApp (E.164). Vazio = sem botão.",
        examples=["+5511988887777"],
    )


class SettingsChanges(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    locale: Literal["pt-BR", "es"] | None = None
    timezone: str | None = Field(default=None, max_length=64)
    buffer_min: int | None = Field(default=None, ge=0, le=120, multiple_of=5)
    slot_step_min: SlotStep | None = None
    min_notice_min: int | None = Field(default=None, ge=0, le=10080, multiple_of=15)
    max_days_ahead: int | None = Field(default=None, ge=1, le=365)
    whatsapp_phone: str | None = Field(
        default=None, max_length=32, description="Como a pessoa digita. Texto vazio tira o botão."
    )


RULE_FIELDS = ("buffer_min", "slot_step_min", "min_notice_min", "max_days_ahead", "whatsapp_phone")


def _whatsapp_or_none(raw: str, country: str) -> str | None:
    if not raw.strip():
        return None
    try:
        return normalize_phone(raw, country)
    except InvalidPhoneError:
        raise ApiError(
            422,
            "validation_error",
            "Telefone inválido",
            fields=[FieldError(field="whatsapp_phone", code="invalid_phone")],
        ) from None


def _out(tenant: TenantContext, db: DbSession) -> TenantSettings:
    options = COUNTRY_TIMEZONES.get(tenant.country, [])
    if tenant.timezone not in options:
        options = [tenant.timezone, *options]
    rules = schedule_settings(db)
    return TenantSettings(
        buffer_min=rules.buffer_min,
        slot_step_min=rules.slot_step_min,
        min_notice_min=rules.min_notice_min,
        max_days_ahead=rules.max_days_ahead,
        whatsapp_phone=rules.whatsapp_phone,
        name=tenant.name,
        locale=tenant.locale,
        timezone=tenant.timezone,
        currency=tenant.currency,
        country=tenant.country,
        timezone_options=options,
    )


@router.get(
    "",
    summary="Ver as configurações",
    description="Nome, idioma padrão, fuso e moeda do estabelecimento.",
    response_model=TenantSettings,
    responses=error_responses(401, 403, 404),
    openapi_extra=permission_doc(Permission.SETTINGS_MANAGE),
)
def get_settings(tenant: TenantDep, db: DbSession, _user: SettingsManager) -> TenantSettings:
    return _out(tenant, db)


@router.patch(
    "",
    summary="Mudar as configurações",
    description=(
        "Só os campos enviados mudam. Vale na hora para todo mundo (página pública, agenda, "
        "e-mails).\n\n"
        "- `buffer_min`: intervalo mínimo entre atendimentos (0 a 120, de 5 em 5).\n"
        "- `slot_step_min`: passo dos horários livres (5, 10, 15, 20, 30 ou 60).\n"
        "- `min_notice_min`: antecedência mínima na página pública (0 a 10080, de 15 em 15).\n"
        "- `max_days_ahead`: até quantos dias à frente a página pública aceita (1 a 365).\n"
        "- `whatsapp_phone`: número do botão na página pública; texto vazio tira o botão.\n"
        "- `422 validation_error` com `fields[0].code`: `invalid_timezone` (fuso desconhecido) ou "
        "`invalid_phone`.\n"
        "- A moeda não muda por aqui (ver `currency`)."
    ),
    response_model=TenantSettings,
    responses=error_responses(401, 403, 404, 422),
    openapi_extra=permission_doc(Permission.SETTINGS_MANAGE),
)
def change_settings(
    payload: SettingsChanges,
    request: Request,
    tenant: TenantDep,
    db: DbSession,
    user: SettingsManager,
) -> TenantSettings:
    changes = payload.model_dump(exclude_none=True)
    if "whatsapp_phone" in changes:
        changes["whatsapp_phone"] = _whatsapp_or_none(changes["whatsapp_phone"], tenant.country)
    rules_changes = {k: changes.pop(k) for k in RULE_FIELDS if k in changes}
    if rules_changes:
        rules = db.get(ScheduleSettings, 1)
        for key, value in rules_changes.items():
            setattr(rules, key, value)
        db.flush()
    if "name" in changes:
        changes["name"] = changes["name"].strip()
        if not changes["name"]:
            raise ApiError(
                422,
                "validation_error",
                "Nome vazio",
                fields=[FieldError(field="name", code="string_too_short")],
            )
    if "timezone" in changes and changes["timezone"] not in available_timezones():
        raise ApiError(
            422,
            "validation_error",
            "Fuso desconhecido",
            fields=[FieldError(field="timezone", code="invalid_timezone")],
        )
    if not changes:
        if rules_changes:
            log.info(
                "schedule_settings_changed",
                tenant_id=str(tenant.id),
                user_id=str(user.id),
                fields=sorted(rules_changes),
            )
        return _out(tenant, db)

    databases = request.app.state.databases
    update_tenant_profile(databases, tenant.id, changes)
    log.info(
        "tenant_settings_changed",
        tenant_id=str(tenant.id),
        user_id=str(user.id),
        fields=sorted([*changes, *rules_changes]),
    )
    return _out(load_tenant(databases, tenant.slug), db)
