"""Serviço do salão = item agendável do core (`Offering`) + preço."""

import uuid

from sqlalchemy import CheckConstraint, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.infra.models import TenantBase
from app.core.scheduling.models import Offering

PRICE_MAX_MINOR = 100_000_000  # R$ 1.000.000,00 ou ₲ 100.000.000: proteção contra erro de digitação


class ServicePrice(TenantBase):
    __tablename__ = "salon_service_prices"
    __table_args__ = (
        CheckConstraint(f"price_minor BETWEEN 0 AND {PRICE_MAX_MINOR}", name="price_minor"),
    )

    offering_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("offerings.id", ondelete="CASCADE"), primary_key=True
    )
    # Na menor unidade da moeda do estabelecimento: centavos (BRL) ou guaranis (PYG).
    price_minor: Mapped[int]

    offering: Mapped[Offering] = relationship(lazy="joined")
