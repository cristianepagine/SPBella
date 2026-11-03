"""Salão: preço de cada serviço

Revision ID: salon_0001_service_prices
Revises: 0005_offerings
Create Date: 2026-11-03

Primeira migração da vertical salon. Depende da tabela offerings do core.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "salon_0001_service_prices"
down_revision: str | None = "0005_offerings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "salon_service_prices",
        sa.Column("offering_id", sa.Uuid(), nullable=False),
        sa.Column("price_minor", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "price_minor BETWEEN 0 AND 100000000", name="ck_salon_service_prices_price_minor"
        ),
        sa.ForeignKeyConstraint(
            ["offering_id"],
            ["offerings.id"],
            name="fk_salon_service_prices_offering_id_offerings",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("offering_id", name="pk_salon_service_prices"),
    )


def downgrade() -> None:
    op.drop_table("salon_service_prices")
