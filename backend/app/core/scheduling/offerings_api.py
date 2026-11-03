"""Itens agendáveis (genérico). Cada vertical tem a sua tela própria (no salão: /services, com
preço); esta lista simples existe para as telas do core (ex.: o que cada profissional faz)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import select

from app.core.accounts.auth import require_permission
from app.core.accounts.models import User
from app.core.accounts.permissions import Permission, permission_doc
from app.core.infra.errors import error_responses
from app.core.infra.tenancy import DbSession
from app.core.scheduling.models import Offering

router = APIRouter(prefix="/t/{slug}/offerings", tags=["Agenda"])


class OfferingOut(BaseModel):
    id: uuid.UUID
    name: str
    duration_min: int
    is_active: bool


@router.get(
    "",
    summary="Listar itens agendáveis",
    description=(
        "Nome e duração de tudo o que pode ser agendado (no salão, os serviços, sem o preço). "
        "Por padrão só os ativos."
    ),
    response_model=list[OfferingOut],
    responses=error_responses(401, 403, 404),
    openapi_extra=permission_doc(Permission.CATALOG_VIEW),
)
def list_offerings(
    db: DbSession,
    _user: Annotated[User, require_permission(Permission.CATALOG_VIEW)],
    include_inactive: Annotated[bool, Query()] = False,
) -> list[OfferingOut]:
    query = select(Offering).order_by(Offering.name)
    if not include_inactive:
        query = query.where(Offering.is_active)
    return [OfferingOut.model_validate(o, from_attributes=True) for o in db.scalars(query)]
