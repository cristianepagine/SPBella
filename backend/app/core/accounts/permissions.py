"""O que cada perfil pode fazer. ESTA tabela é a fonte única de verdade.

- As rotas exigem uma PERMISSÃO (nunca um perfil): `require_permission(Permission.X)`.
- O app recebe as permissões da pessoa em `GET /auth/me` e monta o menu a partir delas.
- tests/test_permissions.py confere a tabela e prova que toda rota recusa (403) quem não pode.

Permissões de funcionalidades que ainda não existem já estão aqui para que a matriz fique
completa e revisável de uma vez; cada história só passa a usá-las.
"""

from enum import StrEnum


class Permission(StrEnum):
    TEAM_MANAGE = "team.manage"  # cadastrar e desativar a equipe (SAL-02)
    SETTINGS_MANAGE = "settings.manage"  # configurações do estabelecimento (SAL-03)
    AUDIT_VIEW = "audit.view"  # quem alterou dados de clientes (SAL-04)
    CATALOG_VIEW = "catalog.view"  # ver a lista de serviços (para agendar) (SAL-05)
    CATALOG_MANAGE = "catalog.manage"  # cadastrar serviços e preços (SAL-05)
    PROVIDERS_MANAGE = "providers.manage"  # profissionais e jornadas (SAL-06)
    CUSTOMERS_MANAGE = "customers.manage"  # cadastrar e buscar clientes (SAL-07)
    AGENDA_VIEW_ALL = "agenda.view_all"  # agenda de todos os profissionais (SAL-08)
    AGENDA_VIEW_OWN = "agenda.view_own"  # só a própria agenda (SAL-08)
    AGENDA_MANAGE = "agenda.manage"  # criar, mover, cancelar, marcar falta (SAL-09)
    TIME_OFF_MANAGE = "time_off.manage"  # bloqueios: almoço, férias, feriado (SAL-10)
    REPORTS_VIEW = "reports.view"  # relatórios e Excel (SAL-16)


ROLE_PERMISSIONS: dict[str, frozenset[Permission]] = {
    "owner": frozenset(Permission),
    "reception": frozenset(
        {
            Permission.CATALOG_VIEW,
            Permission.CUSTOMERS_MANAGE,
            Permission.AGENDA_VIEW_ALL,
            Permission.AGENDA_VIEW_OWN,
            Permission.AGENDA_MANAGE,
        }
    ),
    # "vê só a própria agenda" (e os nomes dos serviços que aparecem nela)
    "professional": frozenset({Permission.AGENDA_VIEW_OWN, Permission.CATALOG_VIEW}),
}

ROLE_NAMES_PT = {"owner": "Dono", "reception": "Recepção", "professional": "Profissional"}


def permissions_for(role: str) -> frozenset[Permission]:
    return ROLE_PERMISSIONS.get(role, frozenset())


def permission_doc(permission: Permission) -> dict:
    """`openapi_extra` da rota: deixa a permissão e os perfis visíveis no openapi.json.

    O teste de permissões usa `x-required-permission` para provar que a rota recusa os demais.
    """
    roles = [role for role, perms in ROLE_PERMISSIONS.items() if permission in perms]
    return {
        "x-required-permission": permission.value,
        "x-allowed-roles": roles,
    }
