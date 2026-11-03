"""Idioma de cada pessoa da equipe

Revision ID: 0003_user_locale
Revises: 0002_auth_tokens
Create Date: 2026-11-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_user_locale"
down_revision: str | None = "0002_auth_tokens"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("locale", sa.String(5), nullable=True))
    op.create_check_constraint(
        "ck_users_locale", "users", "locale IS NULL OR locale IN ('pt-BR', 'es')"
    )


def downgrade() -> None:
    op.drop_constraint("ck_users_locale", "users")
    op.drop_column("users", "locale")
