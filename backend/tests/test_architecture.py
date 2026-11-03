"""Regras de arquitetura que protegem o isolamento entre salões (não precisam de banco)."""

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.infra import tenancy
from app.core.infra.db import DSN_REF_PATTERN
from app.core.infra.tenancy import is_valid_slug, role_for, schema_for
from app.main import create_app

APP_DIR = Path(__file__).resolve().parents[1] / "app"

# Quem pode abrir conexões/sessões por conta própria.
ALLOWED_DB_ACCESS = {"core/infra/db.py", "core/infra/tenancy.py", "core/tenants/provisioning.py"}


def _app_files():
    for path in APP_DIR.rglob("*.py"):
        yield path.relative_to(APP_DIR).as_posix(), path.read_text(encoding="utf-8")


def test_only_core_modules_open_connections_or_sessions():
    pattern = re.compile(r"\b(create_engine|sessionmaker|Session)\(")
    offenders = [name for name, src in _app_files() if pattern.search(src)]

    assert set(offenders) <= ALLOWED_DB_ACCESS, (
        "Use DbSession (app/core/infra/tenancy.py) nas rotas. Arquivos fora da regra: "
        f"{sorted(set(offenders) - ALLOWED_DB_ACCESS)}"
    )


def test_core_never_imports_a_vertical():
    """O core é o template dos próximos sistemas: não pode depender do salão."""
    pattern = re.compile(r"^\s*(from|import) app\.(spbella|registry)\b", re.MULTILINE)
    offenders = [
        name for name, src in _app_files() if name.startswith("core/") and pattern.search(src)
    ]

    assert offenders == [], f"o core importa a vertical em: {offenders}"


def test_only_tenancy_switches_role_or_search_path():
    # Procura SQL de verdade (com aspas), não menções em comentários.
    pattern = re.compile(r"SET (LOCAL )?ROLE \"|'search_path'|SET search_path")
    offenders = {name for name, src in _app_files() if pattern.search(src)}

    assert offenders <= {"core/infra/tenancy.py", "core/tenants/provisioning.py"}


def test_every_salon_route_resolves_the_salon_first(monkeypatch):
    """Toda rota em /t/{slug} precisa passar por get_tenant ANTES de qualquer outra coisa.

    Simulamos "salão não encontrado": todas devem responder 404 tenant_not_found, inclusive
    as que exigem corpo (prova de que o salão é resolvido antes de ler o pedido).
    """
    monkeypatch.setattr(tenancy, "load_tenant", lambda *_: None)
    app = create_app()
    client = TestClient(app, raise_server_exceptions=False)

    checked = 0
    for path, operations in app.openapi()["paths"].items():
        if not path.startswith("/t/"):
            continue
        assert path.startswith("/t/{slug}"), path
        url = re.sub(r"\{[^}]+\}", "00000000-0000-0000-0000-000000000000", path)
        for method in operations:
            response = client.request(method.upper(), url)
            assert response.status_code == 404, f"{method.upper()} {path}"
            assert response.json()["error"]["code"] == "tenant_not_found", f"{method} {path}"
            checked += 1

    assert checked, "nenhuma rota de salão encontrada"


@pytest.mark.parametrize("slug", ["studio-ana", "abc", "salon-2", "a" * 40])
def test_valid_slugs(slug):
    assert is_valid_slug(slug)


@pytest.mark.parametrize(
    "slug", ["ab", "a" * 41, "Studio", "studio_ana", "-ana", "ana-", "an--a", "api", "a b", "ã-b"]
)
def test_invalid_slugs(slug):
    assert not is_valid_slug(slug)


def test_schema_and_role_names():
    assert schema_for("studio-ana") == "t_studio_ana"
    assert role_for("studio-ana", "spbella_") == "spbella_t_studio_ana"


@pytest.mark.parametrize(
    "value", ["DATABASE_URL", "DATABASE_ADMIN_URL", "TENANT_DSN_", "tenant_dsn_x"]
)
def test_dsn_ref_cannot_point_to_other_variables(value):
    assert not DSN_REF_PATTERN.match(value)
