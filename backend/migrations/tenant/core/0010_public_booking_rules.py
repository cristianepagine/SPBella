"""Regras da página pública: antecedência mínima e janela de dias

Revision ID: 0010_public_booking_rules
Revises: 0009_schedule_settings
Create Date: 2026-11-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_public_booking_rules"
down_revision: str | None = "0009_schedule_settings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "schedule_settings",
        sa.Column("min_notice_min", sa.Integer(), server_default=sa.text("60"), nullable=False),
    )
    op.add_column(
        "schedule_settings",
        sa.Column(
            "max_days_ahead", sa.SmallInteger(), server_default=sa.text("60"), nullable=False
        ),
    )
    op.create_check_constraint(
        "ck_schedule_settings_min_notice", "schedule_settings", "min_notice_min BETWEEN 0 AND 10080"
    )
    op.create_check_constraint(
        "ck_schedule_settings_max_days_ahead",
        "schedule_settings",
        "max_days_ahead BETWEEN 1 AND 365",
    )


def downgrade() -> None:
    op.drop_constraint("ck_schedule_settings_max_days_ahead", "schedule_settings")
    op.drop_constraint("ck_schedule_settings_min_notice", "schedule_settings")
    op.drop_column("schedule_settings", "max_days_ahead")
    op.drop_column("schedule_settings", "min_notice_min")
