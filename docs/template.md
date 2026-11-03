# Template: core e verticais

O SPBella (Agenda Salão) é o **primeiro** sistema construído sobre um núcleo reutilizável. O que
serve a qualquer pequeno negócio com agenda fica no **core**; o que é só de salão fica na
**vertical** `salon`. Os próximos sistemas (clínica, pet shop, estúdio...) copiam o core e
escrevem só a vertical deles.

## Onde fica cada coisa

| | Core (template) | Vertical `salon` |
|---|---|---|
| Back-end | `backend/app/core/` | `backend/app/salon/` |
| Migrações de tenant | `backend/migrations/tenant/core/` | `backend/migrations/tenant/salon/` |
| Migrações do `public` | `backend/migrations/public/` | — (só o core) |
| Front-end | `frontend/src/core/` | `frontend/src/salon/` |
| Traduções do front | `frontend/src/core/i18n/locales/` (textos neutros) | `frontend/src/salon/locales/` (vocabulário e textos próprios) |
| Ligação | `backend/app/registry.py` e `frontend/src/App.tsx` + `main.tsx` | |

Módulos do core no back-end:

| Módulo | Conteúdo | História |
|---|---|---|
| `core/infra/` | configuração, banco, isolamento entre tenants, erros, logs, i18n, rate limit, Turnstile, migrações | — |
| `core/tenants/` | tenants (salões), CLI de provisionamento, dados públicos | SAL-01 |
| `core/accounts/` | usuários, perfis, login, senha | SAL-02 |
| `core/system/` | healthcheck | — |
| `core/customers/`, `core/audit/` | clientes, consentimento, auditoria | SAL-04, SAL-07 |
| `core/scheduling/` | profissionais, jornadas, bloqueios, agendamentos, horários livres | SAL-06, 08–10, 13 |
| `core/notifications/` | fila, `NotificationChannel`, e-mail, wa.me | SAL-14, 15 |
| `core/reports/` | relatórios e Excel | SAL-16 |

## Regras

1. **O core nunca importa uma vertical.** Testes garantem isso nos dois lados
   (`backend/tests/test_architecture.py` e `frontend/src/core/architecture.test.ts`).
2. **A vertical se pluga pelo objeto `Vertical`** (`backend/app/core/vertical.py`):

   | Campo | Para quê |
   |---|---|
   | `api_title`, `api_description`, `openapi_tags` | Como a API se apresenta |
   | `routers` | Rotas próprias da vertical |
   | `seed_tenant(session, tenant)` | Dados iniciais de **todo** tenant novo. Roda dentro do `tenants create`, na mesma transação do dono: se falhar, o tenant inteiro é desfeito. |
   | `demo_tenants`, `seed_demo(session, tenant)` | Tenants de demonstração (`tenants seed-demo`) |

   No front, a vertical acrescenta itens ao menu da equipe (`NAV` em `src/App.tsx`, no formato
   `NavItem` de `src/core/layout/nav.ts`) e as rotas dela dentro de `StaffLayout`.

3. **Migrações:** um único histórico do Alembic. Uma migração da vertical pode depender de
   uma do core (`down_revision`), nunca o contrário.
4. **Textos:** o core escreve neutro ("equipe", "estabelecimento"). A vertical troca o
   vocabulário sobrescrevendo as mesmas chaves ("salão") e acrescenta as suas.
5. **Na dúvida, fica na vertical.** Algo só sobe para o core quando um segundo sistema
   precisar dele. Assim o core não cresce com abstrações que ninguém usa.
6. **Permissões:** os perfis (dono, recepção, profissional) e a matriz de permissões são do core
   (`app/core/accounts/permissions.py`). Uma rota da vertical usa
   `require_permission(Permission.X)` e `openapi_extra=permission_doc(Permission.X)`. Se a
   vertical precisar de uma permissão nova, ela entra na matriz do core e no
   `test_permission_matrix`.

## Criando um sistema novo a partir do template

1. Copie o repositório e apague `backend/app/salon/`, `backend/migrations/tenant/salon/` e
   `frontend/src/salon/`.
2. Crie `backend/app/<vertical>/__init__.py` com um `VERTICAL = Vertical(...)` e aponte
   `backend/app/registry.py` para ele.
3. Crie `frontend/src/<vertical>/locales/` (pt-BR e es) e a página pública. Ligue os dois em
   `frontend/src/main.tsx` (`setupI18n`) e `frontend/src/App.tsx` (rota índice do tenant).
4. Ajuste `DIRS` em `frontend/scripts/check-i18n.mjs` e rode todos os testes.
