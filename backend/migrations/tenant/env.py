"""Migrações de UM salão. O schema vem da CLI (atributo `schema`) ou de `-x schema=t_xxx`.

As tabelas são criadas sem schema fixo; o search_path abaixo as coloca no schema do salão.
A tabela alembic_version fica dentro do próprio schema, então cada salão tem sua versão.
"""

import re

from alembic import context
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

import app.core.accounts.models  # noqa: F401 - registra as tabelas do core no metadata
import app.core.audit.models  # noqa: F401
import app.core.customers.models  # noqa: F401
import app.core.scheduling.models  # noqa: F401
import app.registry  # noqa: F401 - e as da vertical
from app.core.infra.config import get_settings
from app.core.infra.models import TenantBase

config = context.config
url = config.attributes.get("url") or get_settings().database_admin_url
if not url:
    raise SystemExit("defina DATABASE_ADMIN_URL no .env")
schema = config.attributes.get("schema") or context.get_x_argument(as_dictionary=True).get("schema")
if not schema or not re.match(r"^[a-z_][a-z0-9_]{0,62}$", schema):
    raise SystemExit("informe o schema do salão: alembic -n tenant -x schema=t_xxx ...")

engine = create_engine(url, poolclass=NullPool)
with engine.connect() as connection:
    connection.execute(text(f'SET search_path TO "{schema}"'))
    connection.commit()
    context.configure(
        connection=connection,
        target_metadata=TenantBase.metadata,
        version_table_schema=schema,
        include_schemas=False,
    )
    with context.begin_transaction():
        context.run_migrations()
