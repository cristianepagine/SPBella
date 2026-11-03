"""Busca de clientes: nome normalizado e índices trigram

Revision ID: 0007_customer_search
Revises: 0006_providers
Create Date: 2026-11-03

Os índices trigram precisam da extensão pg_trgm (criada pelo `db init`). Se ela não existir
no servidor, a migração segue sem os índices: a busca funciona igual, só sem a aceleração.
"""

import re
import unicodedata
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_customer_search"
down_revision: str | None = "0006_providers"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def normalize_text(text: str) -> str:
    """Cópia congelada de app/core/customers/search.py (migração não importa código vivo)."""
    decomposed = unicodedata.normalize("NFKD", text)
    without_accents = "".join(c for c in decomposed if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", without_accents).strip().lower()


def _has_trigram(bind) -> bool:
    return bool(
        bind.execute(sa.text("SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm'")).first()
    )


def upgrade() -> None:
    op.add_column("customers", sa.Column("search_name", sa.String(120), nullable=True))
    bind = op.get_bind()
    for customer_id, name in bind.execute(sa.text("SELECT id, name FROM customers")).all():
        bind.execute(
            sa.text("UPDATE customers SET search_name = :s WHERE id = :id"),
            {"s": normalize_text(name), "id": customer_id},
        )
    op.alter_column("customers", "search_name", nullable=False)
    op.create_index("ix_customers_search_name", "customers", ["search_name"])

    if _has_trigram(bind):
        # pg_trgm fica no schema public; o search_path da migração é só o do tenant.
        op.execute(
            "CREATE INDEX ix_customers_search_name_trgm ON customers "
            "USING gin (search_name public.gin_trgm_ops)"
        )
        op.execute(
            "CREATE INDEX ix_customers_phone_trgm ON customers "
            "USING gin (phone_e164 public.gin_trgm_ops)"
        )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_customers_phone_trgm")
    op.execute("DROP INDEX IF EXISTS ix_customers_search_name_trgm")
    op.drop_index("ix_customers_search_name", "customers")
    op.drop_column("customers", "search_name")
