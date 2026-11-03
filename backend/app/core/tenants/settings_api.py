"""Configurações do estabelecimento (SAL-03): nome, idioma padrão e fuso. Só o dono."""

from typing import Annotated, Literal
from zoneinfo import available_timezones

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from app.core.accounts.auth import require_permission
from app.core.accounts.models import User
from app.core.accounts.permissions import Permission, permission_doc
from app.core.infra.errors import ApiError, FieldError, error_responses
from app.core.infra.logging import log
from app.core.infra.tenancy import TenantContext, TenantDep, load_tenant, update_tenant_profile

router = APIRouter(prefix="/t/{slug}/settings", tags=["Configurações"])

SettingsManager = Annotated[User, require_permission(Permission.SETTINGS_MANAGE)]

# Fusos sugeridos por país (a API aceita qualquer fuso IANA válido).
COUNTRY_TIMEZONES = {
    "BR": [
        "America/Sao_Paulo", "America/Bahia", "America/Fortaleza", "America/Recife",
        "America/Maceio", "America/Belem", "America/Araguaina", "America/Santarem",
        "America/Manaus", "America/Cuiaba", "America/Campo_Grande", "America/Porto_Velho",
        "America/Boa_Vista", "America/Rio_Branco", "America/Noronha",
    ],
    "PY": ["America/Asuncion"],
}  # fmt: skip


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


class SettingsChanges(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    locale: Literal["pt-BR", "es"] | None = None
    timezone: str | None = Field(default=None, max_length=64)


def _out(tenant: TenantContext) -> TenantSettings:
    options = COUNTRY_TIMEZONES.get(tenant.country, [])
    if tenant.timezone not in options:
        options = [tenant.timezone, *options]
    return TenantSettings(
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
def get_settings(tenant: TenantDep, _user: SettingsManager) -> TenantSettings:
    return _out(tenant)


@router.patch(
    "",
    summary="Mudar as configurações",
    description=(
        "Só os campos enviados mudam. Vale na hora para todo mundo (página pública, agenda, "
        "e-mails).\n\n"
        "- `422 validation_error` com `fields[0].code = invalid_timezone`: fuso desconhecido.\n"
        "- A moeda não muda por aqui (ver `currency`)."
    ),
    response_model=TenantSettings,
    responses=error_responses(401, 403, 404, 422),
    openapi_extra=permission_doc(Permission.SETTINGS_MANAGE),
)
def change_settings(
    payload: SettingsChanges, request: Request, tenant: TenantDep, user: SettingsManager
) -> TenantSettings:
    changes = payload.model_dump(exclude_none=True)
    if "name" in changes:
        changes["name"] = changes["name"].strip()
        if not changes["name"]:
            raise ApiError(
                422, "validation_error", "Nome vazio",
                fields=[FieldError(field="name", code="string_too_short")],
            )  # fmt: skip
    if "timezone" in changes and changes["timezone"] not in available_timezones():
        raise ApiError(
            422, "validation_error", "Fuso desconhecido",
            fields=[FieldError(field="timezone", code="invalid_timezone")],
        )  # fmt: skip
    if not changes:
        return _out(tenant)

    databases = request.app.state.databases
    update_tenant_profile(databases, tenant.id, changes)
    log.info(
        "tenant_settings_changed",
        tenant_id=str(tenant.id),
        user_id=str(user.id),
        fields=sorted(changes),
    )
    return _out(load_tenant(databases, tenant.slug))
