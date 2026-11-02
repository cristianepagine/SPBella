"""Tabela de salões (tenants)

Revision ID: 0001_tenants
Revises:
Create Date: 2026-11-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_tenants"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("slug", sa.String(40), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("schema_name", sa.String(63), nullable=False),
        sa.Column("db_role", sa.String(63), nullable=False),
        sa.Column("dsn_ref", sa.String(64), nullable=True),
        sa.Column("country", sa.String(2), nullable=False),
        sa.Column("locale", sa.String(5), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("status", sa.String(16), server_default="provisioning", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("country IN ('BR', 'PY')", name="ck_tenants_country"),
        sa.CheckConstraint("locale IN ('pt-BR', 'es')", name="ck_tenants_locale"),
        sa.CheckConstraint("currency IN ('BRL', 'PYG')", name="ck_tenants_currency"),
        sa.CheckConstraint(
            "status IN ('provisioning', 'active', 'suspended')", name="ck_tenants_status"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_tenants"),
        sa.UniqueConstraint("slug", name="uq_tenants_slug"),
        sa.UniqueConstraint("schema_name", name="uq_tenants_schema_name"),
        sa.UniqueConstraint("db_role", name="uq_tenants_db_role"),
        schema="public",
    )


def downgrade() -> None:
    op.drop_table("tenants", schema="public")
