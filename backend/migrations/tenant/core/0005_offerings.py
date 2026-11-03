"""Itens agendáveis (no salão: serviços)

Revision ID: 0005_offerings
Revises: 0004_customers_audit
Create Date: 2026-11-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_offerings"
down_revision: str | None = "0004_customers_audit"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "offerings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("duration_min", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "duration_min BETWEEN 5 AND 480 AND duration_min % 5 = 0",
            name="ck_offerings_duration",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_offerings"),
    )


def downgrade() -> None:
    op.drop_table("offerings")
