import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import PublicBase


class Tenant(PublicBase):
    __tablename__ = "tenants"
    __table_args__ = (
        CheckConstraint("country IN ('BR', 'PY')", name="country"),
        CheckConstraint("locale IN ('pt-BR', 'es')", name="locale"),
        CheckConstraint("currency IN ('BRL', 'PYG')", name="currency"),
        CheckConstraint("status IN ('provisioning', 'active', 'suspended')", name="status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    slug: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    schema_name: Mapped[str] = mapped_column(String(63), unique=True)
    db_role: Mapped[str] = mapped_column(String(63), unique=True)
    # Nome da variável de ambiente com a conexão do banco dedicado; nulo = banco principal.
    dsn_ref: Mapped[str | None] = mapped_column(String(64))
    country: Mapped[str] = mapped_column(String(2))
    locale: Mapped[str] = mapped_column(String(5))
    timezone: Mapped[str] = mapped_column(String(64))
    currency: Mapped[str] = mapped_column(String(3))
    status: Mapped[str] = mapped_column(String(16), server_default="provisioning")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
