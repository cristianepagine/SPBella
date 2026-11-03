import uuid
from datetime import datetime

from sqlalchemy import ARRAY, DateTime, ForeignKey, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.infra.models import TenantBase


class AuditEntry(TenantBase):
    """Log de auditoria de dados pessoais. SÓ INSERÇÃO: o papel do tenant não tem UPDATE nem
    DELETE nesta tabela, e um trigger barra alterações até do administrador.

    Guarda os NOMES dos campos alterados, nunca os valores.
    """

    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # clock_timestamp(), e não now(): now() é o início da transação, e registros da mesma
    # transação (ex.: cliente criado + consentimento) ficariam com o mesmo horário.
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("clock_timestamp()"), index=True
    )
    # Quem fez: uma pessoa da equipe; nulo quando foi o próprio cliente (página pública) ou o
    # sistema (ver actor_type).
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    actor_type: Mapped[str] = mapped_column(String(16))  # user | customer | system
    action: Mapped[str] = mapped_column(String(48))  # ex.: customer.updated
    entity_type: Mapped[str] = mapped_column(String(32))  # ex.: customer
    entity_id: Mapped[uuid.UUID] = mapped_column(index=True)
    fields: Mapped[list[str]] = mapped_column(ARRAY(String(64)), default=list)
    request_id: Mapped[str | None] = mapped_column(String(64))
