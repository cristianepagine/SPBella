"""Agendamentos, com a trava de banco contra dupla reserva

Revision ID: 0008_appointments
Revises: 0007_customer_search
Create Date: 2026-11-03

A constraint de exclusão precisa da extensão btree_gist (criada pelo `db init`). Ela é
OBRIGATÓRIA: sem ela a migração falha. A única exceção é um Postgres de teste sem extensões,
com ALLOW_MISSING_PG_EXTENSIONS=1 (a aplicação continua validando, mas sem a garantia do banco).
"""

import os
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_appointments"
down_revision: str | None = "0007_customer_search"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EXCLUSION = (
    "ALTER TABLE appointments ADD CONSTRAINT ex_appointments_no_double_booking "
    "EXCLUDE USING gist (provider_id WITH =, tstzrange(starts_at, ends_at, '[)') WITH &&) "
    "WHERE (status IN ('scheduled', 'confirmed'))"
)


def upgrade() -> None:
    op.create_table(
        "appointments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider_id", sa.Uuid(), nullable=False),
        sa.Column("offering_id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(16), server_default="scheduled", nullable=False),
        sa.Column("source", sa.String(16), server_default="staff", nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("starts_at < ends_at", name="ck_appointments_start_before_end"),
        sa.CheckConstraint(
            "status IN ('scheduled', 'confirmed', 'completed', 'no_show', 'cancelled')",
            name="ck_appointments_status",
        ),
        sa.CheckConstraint("source IN ('staff', 'public')", name="ck_appointments_source"),
        sa.ForeignKeyConstraint(
            ["provider_id"], ["providers.id"], name="fk_appointments_provider_id_providers"
        ),
        sa.ForeignKeyConstraint(
            ["offering_id"], ["offerings.id"], name="fk_appointments_offering_id_offerings"
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"], ["customers.id"], name="fk_appointments_customer_id_customers"
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name="fk_appointments_created_by_users"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_appointments"),
    )
    op.create_index("ix_appointments_provider_id", "appointments", ["provider_id"])
    op.create_index("ix_appointments_customer_id", "appointments", ["customer_id"])
    op.create_index("ix_appointments_starts_at", "appointments", ["starts_at"])

    bind = op.get_bind()
    has_gist = bind.execute(
        sa.text("SELECT 1 FROM pg_extension WHERE extname = 'btree_gist'")
    ).first()
    if has_gist:
        # btree_gist fica no schema public; o search_path da migração é só o do tenant, então
        # deixamos o public visível só durante este comando.
        schema = bind.execute(sa.text("SELECT current_schema()")).scalar()
        op.execute(f'SET LOCAL search_path TO "{schema}", public')
        op.execute(EXCLUSION)
    elif os.environ.get("ALLOW_MISSING_PG_EXTENSIONS") != "1":
        raise RuntimeError(
            "btree_gist não está instalada: sem ela não há trava contra dupla reserva. "
            "Rode `db init` num Postgres com a extensão (a imagem oficial já traz)."
        )


def downgrade() -> None:
    op.drop_table("appointments")
