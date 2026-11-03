"""Atalhos para rodar o Alembic pelo código (CLI e testes).

Dois ambientes:
- migrations/public  → tabelas de controle (public.tenants)
- migrations/tenant  → tabelas de cada tenant; roda uma vez por schema. Um histórico ÚNICO,
  com os arquivos em uma pasta por módulo: migrations/tenant/core (template) e
  migrations/tenant/<vertical> (ex.: salon). Um sistema novo copia só a pasta core.
"""

import os
from pathlib import Path
from typing import Literal

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

MIGRATIONS_DIR = Path(__file__).resolve().parents[3] / "migrations"


def tenant_version_dirs() -> list[Path]:
    tenant_dir = MIGRATIONS_DIR / "tenant"
    return sorted(
        d for d in tenant_dir.iterdir() if d.is_dir() and not d.name.startswith(("_", "."))
    )


def alembic_config(
    kind: Literal["public", "tenant"], url: str, schema: str | None = None
) -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR / kind))
    if kind == "tenant":
        config.set_main_option("path_separator", "os")  # separa por os.pathsep
        config.set_main_option(
            "version_locations", os.pathsep.join(str(d) for d in tenant_version_dirs())
        )
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
