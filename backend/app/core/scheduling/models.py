"""Agenda genérica (core).

- `Offering`: o "item agendável" (nome e duração). Preço e o que mais for específico de um tipo
  de negócio ficam na vertical (no salão: app/salon/services/models.py).
- `Provider`: quem atende (no salão, o profissional), com jornada semanal, folgas e os itens
  que realiza. Agendamentos chegam no SAL-09.
"""

import uuid
from datetime import datetime, time

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, SmallInteger, String, Time, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

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


# Cores da agenda (SAL-08). Fixas para combinarem com o tema e terem contraste.
PROVIDER_COLORS = (
    "rose", "violet", "sky", "emerald", "amber", "orange", "teal", "fuchsia", "lime", "slate",
)  # fmt: skip


class Provider(TenantBase):
    __tablename__ = "providers"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120))
    color: Mapped[str] = mapped_column(String(16))
    is_active: Mapped[bool] = mapped_column(server_default=text("true"))
    # Conta de acesso desta pessoa (se ela entra no sistema). Uma conta = um profissional.
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), unique=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    working_hours: Mapped[list["WorkingHours"]] = relationship(
        cascade="all, delete-orphan",
        order_by="(WorkingHours.weekday, WorkingHours.start_time)",
        lazy="selectin",
    )
    offerings: Mapped[list[Offering]] = relationship(
        secondary="provider_offerings", order_by=Offering.name, lazy="selectin"
    )


class ProviderOffering(TenantBase):
    __tablename__ = "provider_offerings"

    provider_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("providers.id", ondelete="CASCADE"), primary_key=True
    )
    offering_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("offerings.id", ondelete="CASCADE"), primary_key=True
    )


class WorkingHours(TenantBase):
    """Uma faixa da jornada semanal, em HORA LOCAL do estabelecimento (não é um instante).

    weekday: 0 = segunda ... 6 = domingo (ISO). Vários registros no mesmo dia = intervalo
    entre eles (ex.: 09:00-12:00 e 13:00-19:00 = almoço das 12h às 13h).
    """

    __tablename__ = "working_hours"
    __table_args__ = (
        CheckConstraint("weekday BETWEEN 0 AND 6", name="weekday"),
        CheckConstraint("start_time < end_time", name="start_before_end"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    provider_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("providers.id", ondelete="CASCADE"), index=True
    )
    weekday: Mapped[int] = mapped_column(SmallInteger)
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)


class TimeOff(TenantBase):
    """Folga, férias ou bloqueio. Instantes em UTC.

    provider_id nulo = vale para todo o estabelecimento (feriado); usado a partir do SAL-10.
    """

    __tablename__ = "time_off"
    __table_args__ = (CheckConstraint("starts_at < ends_at", name="start_before_end"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    provider_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("providers.id", ondelete="CASCADE"), index=True
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# Status que ocupam o horário (os outros liberam o horário para outro agendamento).
ACTIVE_STATUSES = ("scheduled", "confirmed")
APPOINTMENT_STATUSES = ("scheduled", "confirmed", "completed", "no_show", "cancelled")
APPOINTMENT_SOURCES = ("staff", "public")


class Appointment(TenantBase):
    """Agendamento. Instantes em UTC.

    Dupla reserva é impossível: além da validação na aplicação, o banco tem uma constraint de
    exclusão (btree_gist + tstzrange) por profissional, só entre agendamentos ativos.
    O intervalo é [início, fim): um termina às 10h e o outro pode começar às 10h.
    """

    __tablename__ = "appointments"
    __table_args__ = (
        CheckConstraint("starts_at < ends_at", name="start_before_end"),
        CheckConstraint(
            "status IN ('scheduled', 'confirmed', 'completed', 'no_show', 'cancelled')",
            name="status",
        ),
        CheckConstraint("source IN ('staff', 'public')", name="source"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    provider_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("providers.id"), index=True)
    offering_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("offerings.id"))
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id"), index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16), server_default="scheduled")
    source: Mapped[str] = mapped_column(String(16), server_default="staff")
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ScheduleSettings(TenantBase):
    """Regras da agenda do estabelecimento (uma linha só, id = 1)."""

    __tablename__ = "schedule_settings"
    __table_args__ = (
        CheckConstraint("id = 1", name="single_row"),
        CheckConstraint("buffer_min BETWEEN 0 AND 120 AND buffer_min % 5 = 0", name="buffer"),
        CheckConstraint("slot_step_min IN (5, 10, 15, 20, 30, 60)", name="slot_step"),
        CheckConstraint("min_notice_min BETWEEN 0 AND 10080", name="min_notice"),
        CheckConstraint("max_days_ahead BETWEEN 1 AND 365", name="max_days_ahead"),
    )

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, default=1)
    # Intervalo mínimo entre um atendimento e o próximo do mesmo profissional (arrumar, limpar).
    buffer_min: Mapped[int] = mapped_column(SmallInteger, server_default=text("0"))
    # De quantos em quantos minutos os horários livres são oferecidos (9:00, 9:15, 9:30...).
    slot_step_min: Mapped[int] = mapped_column(SmallInteger, server_default=text("15"))
    # Página pública: antecedência mínima para marcar (minutos) e até quantos dias à frente.
    min_notice_min: Mapped[int] = mapped_column(server_default=text("60"))
    max_days_ahead: Mapped[int] = mapped_column(SmallInteger, server_default=text("60"))
