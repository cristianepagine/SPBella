"""SAL-02: cada perfil só faz o que pode. Acesso indevido = 403, testado em TODAS as rotas.

A varredura lê o openapi.json: toda rota em /t/{slug} precisa declarar a permissão
(`openapi_extra=permission_doc(...)`) ou estar na lista de rotas abertas abaixo. Assim, uma rota
nova que esquecer a permissão faz este teste falhar.
"""

import re

import pytest

from app.core.accounts.permissions import ROLE_PERMISSIONS, Permission
from app.main import create_app
from tests.test_auth import access_token, bearer

ROLES = ("owner", "reception", "professional")

# Rotas sem permissão específica: públicas, ou para qualquer pessoa logada (a própria conta).
OPEN_ROUTES = {
    ("get", "/t/{slug}"),
    ("post", "/t/{slug}/auth/login"),
    ("post", "/t/{slug}/auth/refresh"),
    ("post", "/t/{slug}/auth/logout"),
    ("get", "/t/{slug}/auth/me"),
    ("patch", "/t/{slug}/auth/me"),
    ("post", "/t/{slug}/auth/change-password"),
    ("post", "/t/{slug}/auth/forgot-password"),
    ("post", "/t/{slug}/auth/reset-password"),
}

ANY_ID = "00000000-0000-0000-0000-000000000000"


def _protected_operations() -> list[tuple[str, str, dict]]:
    spec = create_app().openapi()
    return [
        (method, path, operation)
        for path, operations in spec["paths"].items()
        if path.startswith("/t/")
        for method, operation in operations.items()
        if (method, path) not in OPEN_ROUTES
    ]


def _url(path: str, slug: str = "alpha") -> str:
    return re.sub(r"\{[^}]+\}", ANY_ID, path.replace("{slug}", slug))


# --- a tabela ----------------------------------------------------------------------------


def test_permission_matrix():
    """A matriz combinada na especificação (dono, recepção, profissional)."""
    assert ROLE_PERMISSIONS["owner"] == frozenset(Permission)
    assert ROLE_PERMISSIONS["reception"] == {
        Permission.CUSTOMERS_MANAGE,
        Permission.AGENDA_VIEW_ALL,
        Permission.AGENDA_VIEW_OWN,
        Permission.AGENDA_MANAGE,
    }
    assert ROLE_PERMISSIONS["professional"] == {Permission.AGENDA_VIEW_OWN}


def test_every_salon_route_declares_its_permission():
    operations = _protected_operations()
    assert operations, "nenhuma rota protegida encontrada"

    for method, path, operation in operations:
        where = f"{method.upper()} {path}"
        assert "x-required-permission" in operation, f"{where}: declare permission_doc(...)"
        permission = Permission(operation["x-required-permission"])
        expected_roles = [r for r in ROLES if permission in ROLE_PERMISSIONS[r]]
        assert operation["x-allowed-roles"] == expected_roles, where


# --- a prova, com banco ------------------------------------------------------------------


@pytest.mark.parametrize("role", ROLES)
def test_routes_refuse_roles_without_permission(db_client, make_user, role):
    token = access_token(db_client, make_user("alpha", role=role))
    checked = 0

    for method, path, operation in _protected_operations():
        allowed = role in operation["x-allowed-roles"]
        response = db_client.request(method.upper(), _url(path), headers=bearer(token), json={})
        where = f"{role} {method.upper()} {path}"
        if allowed:
            assert response.status_code not in (401, 403), where
        else:
            assert response.status_code == 403, where
            assert response.json()["error"]["code"] == "forbidden", where
        checked += 1

    assert checked > 0


def test_protected_routes_require_login(db_client):
    for method, path, _ in _protected_operations():
        response = db_client.request(method.upper(), _url(path), json={})
        assert response.status_code == 401, f"{method.upper()} {path}"
