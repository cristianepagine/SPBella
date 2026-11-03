"""Registro no log de auditoria. Chame na MESMA transação da mudança: se a mudança for
desfeita, o registro também é; se o registro falhar, a mudança não acontece."""

import uuid
from collections.abc import Iterable

from fastapi import Request
from sqlalchemy.orm import Session

from app.core.accounts.models import User
from app.core.audit.models import AuditEntry


def record(
    db: Session,
    request: Request | None,
    *,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID,
    actor: User | None,
    actor_type: str = "user",
    fields: Iterable[str] = (),
) -> None:
    """`fields`: NOMES dos campos envolvidos (ex.: ["phone"]). Nunca passe valores."""
    db.add(
        AuditEntry(
            id=uuid.uuid4(),
            actor_user_id=actor.id if actor else None,
            actor_type=actor_type if actor is None else "user",
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            fields=sorted(set(fields)),
            request_id=getattr(request.state, "request_id", None) if request else None,
        )
    )
