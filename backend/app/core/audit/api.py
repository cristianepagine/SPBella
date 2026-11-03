"""Consulta do log de auditoria (SAL-04): quem criou, viu ou alterou dados pessoais, e quando."""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.accounts.auth import require_permission
from app.core.accounts.models import User
from app.core.accounts.permissions import Permission, permission_doc
from app.core.audit.models import AuditEntry
from app.core.infra.errors import error_responses
from app.core.infra.tenancy import DbSession

router = APIRouter(prefix="/t/{slug}/audit", tags=["Auditoria"])

AuditViewer = Annotated[User, require_permission(Permission.AUDIT_VIEW)]

ACTIONS_DOC = (
    "`customer.created`, `customer.viewed` (alguém abriu a ficha), `customer.updated`, "
    "`consent.granted`, `consent.revoked`"
)


class Actor(BaseModel):
    id: uuid.UUID
    name: str


class AuditEntryOut(BaseModel):
    id: uuid.UUID
    occurred_at: datetime
    action: str = Field(description=f"O que aconteceu: {ACTIONS_DOC}.")
    entity_type: str = Field(examples=["customer"])
    entity_id: uuid.UUID
    actor_type: Literal["user", "customer", "system"] = Field(
        description="`user` = pessoa da equipe (ver `actor`); `customer` = o próprio cliente, "
        "pela página pública; `system` = o sistema."
    )
    actor: Actor | None
    fields: list[str] = Field(
        description="Nomes dos campos envolvidos (ex.: `phone`). Os valores nunca são guardados.",
        examples=[["email", "phone"]],
    )


@router.get(
    "",
    summary="Consultar o log de auditoria",
    description=(
        "Registros mais recentes primeiro. Filtre por `entity_id` (ex.: o ID de um cliente) "
        "para ver o histórico de uma ficha. Para ver mais, repita a chamada com "
        "`before` = `occurred_at` do último registro recebido.\n\n"
        "O log só aceita inclusão: ninguém, nem o dono, consegue alterar ou apagar registros."
    ),
    response_model=list[AuditEntryOut],
    responses=error_responses(401, 403, 404, 422),
    openapi_extra=permission_doc(Permission.AUDIT_VIEW),
)
def list_audit(
    db: DbSession,
    _user: AuditViewer,
    entity_id: Annotated[uuid.UUID | None, Query(description="Só deste registro.")] = None,
    before: Annotated[datetime | None, Query(description="Só antes deste instante.")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[AuditEntryOut]:
    query = (
        select(AuditEntry, User.name)
        .outerjoin(User, User.id == AuditEntry.actor_user_id)
        .order_by(AuditEntry.occurred_at.desc(), AuditEntry.id)
        .limit(limit)
    )
    if entity_id:
        query = query.where(AuditEntry.entity_id == entity_id)
    if before:
        query = query.where(AuditEntry.occurred_at < before)
    return [
        AuditEntryOut(
            id=entry.id,
            occurred_at=entry.occurred_at,
            action=entry.action,
            entity_type=entry.entity_type,
            entity_id=entry.entity_id,
            actor_type=entry.actor_type,
            actor=Actor(id=entry.actor_user_id, name=name) if entry.actor_user_id else None,
            fields=entry.fields,
        )
        for entry, name in db.execute(query)
    ]
