"""Regras da agenda: intervalo mínimo entre atendimentos e passo dos horários livres

Revision ID: 0009_schedule_settings
Revises: 0008_appointments
Create Date: 2026-11-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_schedule_settings"
down_revision: str | None = "0008_appointments"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "schedule_settings",
        sa.Column("id", sa.SmallInteger(), nullable=False),
        sa.Column("buffer_min", sa.SmallInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("slot_step_min", sa.SmallInteger(), server_default=sa.text("15"), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_schedule_settings_single_row"),
        sa.CheckConstraint(
            "buffer_min BETWEEN 0 AND 120 AND buffer_min % 5 = 0",
            name="ck_schedule_settings_buffer",
        ),
        sa.CheckConstraint(
            "slot_step_min IN (5, 10, 15, 20, 30, 60)", name="ck_schedule_settings_slot_step"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_schedule_settings"),
    )
    op.execute("INSERT INTO schedule_settings (id) VALUES (1)")


def downgrade() -> None:
    op.drop_table("schedule_settings")
