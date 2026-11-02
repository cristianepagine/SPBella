"""Atalhos para rodar o Alembic pelo código (CLI e testes).

Dois ambientes:
- migrations/public  → tabelas de controle (public.tenants)
- migrations/tenant  → tabelas de cada salão; roda uma vez por schema
"""

from pathlib import Path
from typing import Literal

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"


def alembic_config(
    kind: Literal["public", "tenant"], url: str, schema: str | None = None
) -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR / kind))
    config.attributes["url"] = url
    config.attributes["schema"] = schema
    return config


def upgrade_public(admin_url: str) -> None:
    command.upgrade(alembic_config("public", admin_url), "head")


def upgrade_tenant(admin_url: str, schema: str) -> None:
    command.upgrade(alembic_config("tenant", admin_url, schema), "head")


def tenant_head() -> str:
    script = ScriptDirectory.from_config(alembic_config("tenant", ""))
    head = script.get_current_head()
    assert head is not None
    return head
