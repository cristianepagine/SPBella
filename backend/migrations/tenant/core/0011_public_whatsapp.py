"""WhatsApp do estabelecimento, para o botão da página pública

Revision ID: 0011_public_whatsapp
Revises: 0010_public_booking_rules
Create Date: 2026-11-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011_public_whatsapp"
down_revision: str | None = "0010_public_booking_rules"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("schedule_settings", sa.Column("whatsapp_phone", sa.String(16), nullable=True))


def downgrade() -> None:
    op.drop_column("schedule_settings", "whatsapp_phone")
