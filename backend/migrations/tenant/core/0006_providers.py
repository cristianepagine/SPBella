"""Profissionais, jornada semanal, itens que cada um realiza e folgas

Revision ID: 0006_providers
Revises: 0005_offerings
Create Date: 2026-11-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_providers"
down_revision: str | None = "0005_offerings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamp(name: str) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)


def upgrade() -> None:
    op.create_table(
        "providers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("color", sa.String(16), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        _timestamp("created_at"),
        _timestamp("updated_at"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_providers_user_id_users", ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_providers"),
        sa.UniqueConstraint("user_id", name="uq_providers_user_id"),
    )

    op.create_table(
        "provider_offerings",
        sa.Column("provider_id", sa.Uuid(), nullable=False),
        sa.Column("offering_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["provider_id"],
            ["providers.id"],
            name="fk_provider_offerings_provider_id_providers",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["offering_id"],
            ["offerings.id"],
            name="fk_provider_offerings_offering_id_offerings",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("provider_id", "offering_id", name="pk_provider_offerings"),
    )

    op.create_table(
        "working_hours",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider_id", sa.Uuid(), nullable=False),
        sa.Column("weekday", sa.SmallInteger(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.CheckConstraint("weekday BETWEEN 0 AND 6", name="ck_working_hours_weekday"),
        sa.CheckConstraint("start_time < end_time", name="ck_working_hours_start_before_end"),
        sa.ForeignKeyConstraint(
            ["provider_id"],
            ["providers.id"],
            name="fk_working_hours_provider_id_providers",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_working_hours"),
    )
    op.create_index("ix_working_hours_provider_id", "working_hours", ["provider_id"])

    op.create_table(
        "time_off",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider_id", sa.Uuid(), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.String(120), nullable=True),
        _timestamp("created_at"),
        sa.CheckConstraint("starts_at < ends_at", name="ck_time_off_start_before_end"),
        sa.ForeignKeyConstraint(
            ["provider_id"],
            ["providers.id"],
            name="fk_time_off_provider_id_providers",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_time_off"),
    )
    op.create_index("ix_time_off_provider_id", "time_off", ["provider_id"])


def downgrade() -> None:
    op.drop_table("time_off")
    op.drop_table("working_hours")
    op.drop_table("provider_offerings")
    op.drop_table("providers")
