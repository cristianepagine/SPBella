"""Atalhos para rodar o Alembic pelo código (CLI e testes).

Dois ambientes:
- migrations/public  → tabelas de controle (public.tenants)
- migrations/tenant  → tabelas de cada tenant; roda uma vez por schema. Uma pasta por módulo:
  migrations/tenant/core (template, sequência própria) e migrations/tenant/<vertical>
  (um RAMO do Alembic, com branch_labels=("<vertical>",), que declara depends_on nas migrações
  do core de que precisa). O core nunca depende da vertical: um sistema novo copia só a pasta
  core. Por isso há um "head" por módulo, e o upgrade é sempre para "heads".
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
    command.upgrade(alembic_config("tenant", admin_url, schema), "heads")


def tenant_heads() -> list[str]:
    """Última migração de cada módulo (core e vertical), em ordem alfabética."""
    return sorted(ScriptDirectory.from_config(alembic_config("tenant", "")).get_heads())


def tenant_head() -> str:
    """Versão de um tenant em dia, como `tenants list` mostra: "0006_x+salon_0001_y"."""
    return "+".join(tenant_heads())
