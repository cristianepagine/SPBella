# Arquitetura e decisões

Registro das decisões aprovadas na proposta inicial (2026-11-02). Quando uma decisão mudar,
atualize este arquivo dizendo o que mudou e por quê.

## Visão geral

```
Celular (PWA) ── app.<dominio>/{slug}   ──►  Cloudflare Pages (frontend/)
Página pública ─ <dominio>/{slug}       ──►  Cloudflare Pages
           │ fetch
           ▼
api.<dominio>/t/{slug}/... ─► Cloudflare (WAF, rate limit) ─► Cloudflare Tunnel ─► VPS São Paulo
                                                                 ├─ api (backend/, FastAPI)
                                                                 ├─ worker (fila e lembretes)
                                                                 ├─ postgres
                                                                 └─ backup (pg_dump → age → R2)
```

## Decisões

| Tema | Decisão | Motivo |
|---|---|---|
| Repositório | Um repositório, projetos `backend/` e `frontend/` independentes | Mudança de API e tela no mesmo commit; tipos do front gerados do OpenAPI |
| Tenant na URL | Slug no caminho (`/t/{slug}`), não subdomínio | Pages não aceita domínio curinga sem Worker; um PWA só |
| Isolamento | Schema por salão + papel do Postgres por salão; `SET LOCAL ROLE` e `SET LOCAL search_path` em um único ponto | Mesmo com bug no código, o banco nega acesso a outro salão |
| Banco dedicado | `tenants.dsn_ref` aponta para uma variável de ambiente com a conexão | Migrar um cliente sem mudar código e sem senha no banco |
| Acesso ao banco | SQLAlchemy 2.0 **síncrono** + psycopg 3 | Mais simples; o mesmo código serve API, CLI e worker |
| Migrações | Alembic com dois ambientes: `migrations/public` e `migrations/tenant` (um `alembic_version` por schema) | Cada salão evolui de forma independente; `tenants migrate --all` segue em frente se um falhar |
| Fila | Tabela `public.jobs` com `FOR UPDATE SKIP LOCKED` + `LISTEN/NOTIFY` | Sem Redis, custo menor |
| Erros | `{"error": {"code", ...}}`; o front traduz o `code` | Nenhum texto para o usuário fixo no back-end |
| Logs | JSON (structlog), filtro de dados pessoais, sem query string nem corpo | LGPD |
| Hospedagem | VPS em São Paulo, sem portas abertas (Cloudflare Tunnel) | Latência no celular; dados de clientes do BR ficam no Brasil |
| Python | 3.12, dependências gerenciadas com `uv` | Versão pedida; `uv` instala a versão certa sozinho |
| TypeScript | 5.9 (não 7) | O gerador de tipos `openapi-typescript` ainda não roda no TypeScript 7 nativo |
| Datas | UTC no banco; fuso IANA por salão | Brasil e Paraguai sem horário de verão hoje, mas tzdata cobre mudanças futuras |
| Dinheiro | Inteiro na menor unidade (`*_minor`) | Sem erro de arredondamento; PYG não tem centavos |

## Isolamento entre salões (história 2)

**Papéis no Postgres:**
- **Administrador** (`DATABASE_ADMIN_URL`): é dono dos schemas e das tabelas, e roda as migrações. Só a CLI usa.
- **Aplicação** (`DATABASE_URL`, ex.: `spbella_app`):
  - `LOGIN NOINHERIT`;
  - lê `public.tenants`;
  - é membro de todos os papéis de salão, mas, por causa do `NOINHERIT`, **não acessa nenhuma tabela de salão sem `SET ROLE`**.
- **Um papel por salão** (`spbella_t_<slug>`): `NOLOGIN`. Lê e grava só nas tabelas do próprio schema. Não cria, altera nem apaga estrutura, e não lê `public.tenants`.

**Como uma sessão entra no salão:** só [app/core/tenancy.py](../backend/app/core/tenancy.py) faz isso. A cada transação ele executa `SET LOCAL ROLE` e `set_config('search_path', ..., true)`. Os dois valem só até o fim da transação, então a conexão volta limpa para o pool. As rotas recebem essa sessão pela dependência `DbSession`, com `scope="function"`: o commit acontece antes de a resposta sair.

**O que os testes provam** ([tests/test_tenant_isolation.py](../backend/tests/test_tenant_isolation.py)):
- por HTTP, o salão B não lista, não lê, não altera e não apaga registros do salão A, nem mesmo pelo ID;
- o papel do salão B, ao consultar ou gravar `t_alpha.*` diretamente, é **negado pelo Postgres**;
- o papel de um salão não altera estrutura nem lê a lista de salões;
- o papel da aplicação, sozinho, não lê tabelas de salão;
- a conexão volta ao pool sem papel nem search_path do pedido anterior;
- 60 sessões em paralelo, alternando A e B, nunca se misturam;
- erro na rota desfaz tudo (rollback);
- salão em banco dedicado grava no banco dele;
- toda rota em `/t/{slug}` resolve o salão antes de qualquer outra coisa.

**Limite conhecido:** o Postgres decide quem pode fazer `SET ROLE` olhando o usuário da
**conexão** (o papel da aplicação, membro de todos os salões), e não o papel atual. Então, se
houvesse **SQL injection**, o código injetado poderia trocar para o papel de outro salão. As
defesas contra isso:
1. Todo SQL é parametrizado (ORM ou `text()` com parâmetros). O lint (regra `S608`) barra SQL
   montado com texto.
2. Um teste garante que só `tenancy.py` (e a CLI de provisionamento) executa `SET ROLE` ou altera o `search_path`.

A alternativa que fecha também esse caso é um papel **com login** por salão: cada salão teria o
próprio pool de conexões, o que pede PgBouncer quando houver muitos salões. Está no backlog
para quando o número de salões ou um contrato justificarem.

**Mudanças em relação à proposta inicial:**
- A tabela `public.tenant_migrations` não foi criada. A versão de cada salão fica na
  `alembic_version` do próprio schema (`tenants list` mostra), e os erros de migração aparecem na saída de
  `tenants migrate`, que devolve código 1 se algum salão falhar.
- `global_settings` fica para quando houver a primeira configuração global de verdade.
- `public.jobs` entra na história 9 (fila).

## Pontos de atenção legais

- **LGPD:** o salão é o **controlador** e a Spartacus é a **operadora** → contrato de operador
  nos termos de uso. Salões pequenos estão dispensados de nomear encarregado (Res. CD/ANPD nº 2/2022),
  mas precisam oferecer um canal de contato ao titular.
- **Paraguai:** aplicamos o padrão da LGPD. A lei geral paraguaia de proteção de dados (2025) tem
  prazo de adequação; **confirmar número, prazos e exigências com advogado local**. Hospedar no
  Brasil é transferência internacional para dados paraguaios. Dados de inadimplência, se um dia
  existirem, seguem também a Ley 6534/2020.
- No código, pontos onde a norma paraguaia pode pedir algo a mais são marcados com `# PY-LEGAL:`.
