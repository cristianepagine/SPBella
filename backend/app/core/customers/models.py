import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.infra.models import TenantBase

# Para que os dados do cliente são usados. "service" (o atendimento em si) é obrigatório.
CONSENT_PURPOSES = ("service", "reminders", "marketing")
CONSENT_SOURCES = ("staff", "public_booking")


class Customer(TenantBase):
    __tablename__ = "customers"
    __table_args__ = (
        CheckConstraint("locale IS NULL OR locale IN ('pt-BR', 'es')", name="locale"),
        CheckConstraint("email IS NULL OR email = lower(email)", name="email_lowercase"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120))
    # Sempre no formato internacional E.164 (+5511988887777), validado pelo phonenumbers.
    phone_e164: Mapped[str] = mapped_column(String(16), index=True)
    email: Mapped[str | None] = mapped_column(String(254))
    # Idioma das mensagens para o cliente; nulo = idioma padrão do estabelecimento.
    locale: Mapped[str | None] = mapped_column(String(5))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    consents: Mapped[list["Consent"]] = relationship(
        back_populates="customer", order_by="Consent.granted_at", lazy="selectin"
    )

    def active_consents(self) -> list["Consent"]:
        return [c for c in self.consents if c.revoked_at is None]


class Consent(TenantBase):
    """Histórico de consentimentos: cada concessão é uma linha; revogar preenche revoked_at."""

    __tablename__ = "consents"
    __table_args__ = (
        CheckConstraint("purpose IN ('service', 'reminders', 'marketing')", name="purpose"),
        CheckConstraint("source IN ('staff', 'public_booking')", name="source"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"), index=True
    )
    purpose: Mapped[str] = mapped_column(String(16))
    policy_version: Mapped[str] = mapped_column(String(32))
    source: Mapped[str] = mapped_column(String(16))
    # Quem registrou (recepção/dono); nulo quando veio da página pública.
    recorded_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    customer: Mapped[Customer] = relationship(back_populates="consents")
