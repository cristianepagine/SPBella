"""Clientes, consentimentos e log de auditoria (só inserção)

Revision ID: 0004_customers_audit
Revises: 0003_user_locale
Create Date: 2026-11-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_customers_audit"
down_revision: str | None = "0003_user_locale"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamp(name: str) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)


def upgrade() -> None:
    op.create_table(
        "customers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("phone_e164", sa.String(16), nullable=False),
        sa.Column("email", sa.String(254), nullable=True),
        sa.Column("locale", sa.String(5), nullable=True),
        _timestamp("created_at"),
        _timestamp("updated_at"),
        sa.CheckConstraint(
            "locale IS NULL OR locale IN ('pt-BR', 'es')", name="ck_customers_locale"
        ),
        sa.CheckConstraint(
            "email IS NULL OR email = lower(email)", name="ck_customers_email_lowercase"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_customers"),
    )
    op.create_index("ix_customers_phone_e164", "customers", ["phone_e164"])

    op.create_table(
        "consents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("purpose", sa.String(16), nullable=False),
        sa.Column("policy_version", sa.String(32), nullable=False),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("recorded_by", sa.Uuid(), nullable=True),
        _timestamp("granted_at"),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "purpose IN ('service', 'reminders', 'marketing')", name="ck_consents_purpose"
        ),
        sa.CheckConstraint("source IN ('staff', 'public_booking')", name="ck_consents_source"),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            name="fk_consents_customer_id_customers",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["recorded_by"], ["users.id"], name="fk_consents_recorded_by_users"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_consents"),
    )
    op.create_index("ix_consents_customer_id", "consents", ["customer_id"])

    op.create_table(
        "audit_log",
        sa.Column("id", sa.Uuid(), nullable=False),
        # clock_timestamp(): horário real de cada registro, mesmo dentro da mesma transação
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("actor_type", sa.String(16), nullable=False),
        sa.Column("action", sa.String(48), nullable=False),
        sa.Column("entity_type", sa.String(32), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("fields", sa.ARRAY(sa.String(64)), nullable=False, server_default="{}"),
        sa.Column("request_id", sa.String(64), nullable=True),
        sa.ForeignKeyConstraint(
            ["actor_user_id"], ["users.id"], name="fk_audit_log_actor_user_id_users"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_audit_log"),
    )
    op.create_index("ix_audit_log_occurred_at", "audit_log", ["occurred_at"])
    op.create_index("ix_audit_log_entity_id", "audit_log", ["entity_id"])

    # Só inserção, inclusive para o administrador. (O papel do tenant também não recebe
    # UPDATE/DELETE: ver APPEND_ONLY_TABLES em provisioning.py.)
    op.execute(
        """
        CREATE FUNCTION audit_log_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'audit_log aceita somente INSERT' USING ERRCODE = '42501';
        END;
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER audit_log_append_only BEFORE UPDATE OR DELETE ON audit_log "
        "FOR EACH ROW EXECUTE FUNCTION audit_log_append_only()"
    )
    op.execute(
        "CREATE TRIGGER audit_log_no_truncate BEFORE TRUNCATE ON audit_log "
        "FOR EACH STATEMENT EXECUTE FUNCTION audit_log_append_only()"
    )


def downgrade() -> None:
    op.drop_table("audit_log")
    op.execute("DROP FUNCTION audit_log_append_only()")
    op.drop_table("consents")
    op.drop_table("customers")
