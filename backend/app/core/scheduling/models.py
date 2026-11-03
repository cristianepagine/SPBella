"""Agenda genérica (core). Profissionais, jornadas, bloqueios e agendamentos chegam no SAL-06+.

`Offering` é o "item agendável": tem nome e duração. Preço e o resto do que é específico de um
tipo de negócio ficam na vertical (no salão: app/salon/services/models.py).
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.infra.models import TenantBase

DURATION_STEP_MIN = 5
DURATION_MAX_MIN = 480


class Offering(TenantBase):
    __tablename__ = "offerings"
    __table_args__ = (
        CheckConstraint(
            f"duration_min BETWEEN {DURATION_STEP_MIN} AND {DURATION_MAX_MIN} "
            f"AND duration_min % {DURATION_STEP_MIN} = 0",
            name="duration",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120))
    duration_min: Mapped[int]
    # Desativar em vez de apagar: agendamentos antigos continuam apontando para o item.
    is_active: Mapped[bool] = mapped_column(server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
