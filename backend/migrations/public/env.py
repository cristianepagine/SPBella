"""Migrações do schema public. Rodam com o papel administrador."""

from alembic import context
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.models.base import PublicBase
from app.models.public import Tenant  # noqa: F401 - registra a tabela no metadata

config = context.config
url = config.attributes.get("url") or get_settings().database_admin_url
if not url:
    raise SystemExit("defina DATABASE_ADMIN_URL no .env")

engine = create_engine(url, poolclass=NullPool)
with engine.connect() as connection:
    context.configure(
        connection=connection,
        target_metadata=PublicBase.metadata,
        version_table_schema="public",
        include_schemas=False,
    )
    with context.begin_transaction():
        context.run_migrations()
