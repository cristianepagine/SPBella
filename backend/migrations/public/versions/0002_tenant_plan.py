"""Plano do tenant (base ou com WhatsApp automático)

Revision ID: 0002_tenant_plan
Revises: 0001_tenants
Create Date: 2026-11-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_tenant_plan"
down_revision: str | None = "0001_tenants"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("plan", sa.String(32), server_default="base", nullable=False),
        schema="public",
    )
    op.create_check_constraint(
        "ck_tenants_plan", "tenants", "plan IN ('base', 'whatsapp_api')", schema="public"
    )


def downgrade() -> None:
    op.drop_constraint("ck_tenants_plan", "tenants", schema="public")
    op.drop_column("tenants", "plan", schema="public")
