from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.infra.errors import error_responses
from app.core.infra.tenancy import TenantDep

router = APIRouter(prefix="/t/{slug}", tags=["Estabelecimento"])


class TenantPublicInfo(BaseModel):
    slug: str = Field(examples=["studio-bella"])
    name: str = Field(examples=["Studio Bella"])
    country: Literal["BR", "PY"]
    locale: Literal["pt-BR", "es"] = Field(description="Idioma padrão do salão.")
    timezone: str = Field(description="Fuso horário IANA do salão.", examples=["America/Sao_Paulo"])
    currency: Literal["BRL", "PYG"] = Field(description="Moeda dos valores `*_minor`.")


@router.get(
    "",
    summary="Dados públicos do salão",
    description=(
        "Nome, idioma, fuso e moeda do salão. Usado pelo app e pela página de agendamento "
        "para se apresentar e formatar datas e valores. Não exige login e não traz dados "
        "pessoais. Salão inexistente ou suspenso responde 404 `tenant_not_found`."
    ),
    response_model=TenantPublicInfo,
    responses=error_responses(404),
)
def get_public_info(tenant: TenantDep) -> TenantPublicInfo:
    return TenantPublicInfo(
        slug=tenant.slug,
        name=tenant.name,
        country=tenant.country,
        locale=tenant.locale,
        timezone=tenant.timezone,
        currency=tenant.currency,
    )
