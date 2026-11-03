# SPBella

**Agenda Salão**: sistema de agendamento para salões e barbearias, feito pela
**Spartacus Soluções**. Usado no celular, em português (Brasil) e espanhol (Paraguai).

É também o **template base** dos próximos sistemas: o que é genérico mora em `core` e o que é
só de salão, em `salon`. Ver [docs/template.md](docs/template.md).

## Estrutura

| Pasta | O que é |
|---|---|
| [`backend/`](backend/) | API em Python 3.12 + FastAPI + SQLAlchemy 2 + Postgres. `app/core` (template) e `app/salon` (vertical) |
| [`frontend/`](frontend/) | App React + TypeScript + Vite + Tailwind (PWA). `src/core` (template) e `src/salon` (vertical) |
| [`docs/template.md`](docs/template.md) | Como o core e as verticais se encaixam, e como criar um sistema novo |
| [`docs/api/`](docs/api/) | **Documentação da API**: guia, `openapi.json` e changelog |
| [`docs/arquitetura.md`](docs/arquitetura.md) | Decisões de arquitetura e pontos legais |
| [`docs/backlog.md`](docs/backlog.md) | Histórias do MVP e o que fica para depois |

## Pré-requisitos

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Postgres e API)
- [uv](https://docs.astral.sh/uv/) para o back-end (`pip install uv`). Ele instala o Python 3.12 sozinho.
- Node.js 24 para o front-end

## Rodando em desenvolvimento

```bash
cp .env.example .env              # e troque POSTGRES_PASSWORD e APP_DB_PASSWORD
docker compose up --build         # Postgres + API em http://localhost:8000

# dados de demonstração (só na primeira vez)
docker compose exec api python -m app.cli tenants seed-demo

cd frontend
cp .env.example .env
npm install
npm run dev                       # app em http://localhost:5173
```

- Abra <http://localhost:5173/studio-bella> (Brasil) ou <http://localhost:5173/salon-asuncion> (Paraguai)
  e clique em **Área do salão: entrar**. Cada salão de demonstração tem um acesso de cada perfil,
  todos com a senha `demo-spbella`:

  | Perfil | Studio Bella (BR) | Salón Asunción (PY) |
  |---|---|---|
  | Dono | `dono@studio-bella.demo` | `duena@salon-asuncion.demo` |
  | Recepção | `recepcao@studio-bella.demo` | `recepcion@salon-asuncion.demo` |
  | Profissional | `profissional@studio-bella.demo` | `profesional@salon-asuncion.demo` |
- Em desenvolvimento, os e-mails (ex.: "esqueci a senha") aparecem no terminal da API
  (`docker compose logs -f api`).
- Documentação interativa da API: <http://localhost:8000/docs> (Swagger) e <http://localhost:8000/redoc>.
- A API recarrega sozinha quando um arquivo em `backend/app/` é salvo. A cada subida, o compose roda
  `db init` e `tenants migrate --all`.

### Back-end sem Docker

```bash
cd backend
uv sync --python 3.12
# no .env da raiz, descomente DATABASE_URL e DATABASE_ADMIN_URL apontando para localhost
uv run python -m app.cli db init
uv run uvicorn app.main:app --reload
```

## Salões (tenants)

Cada salão tem um schema próprio no Postgres (`t_<slug>`) e um papel próprio que só enxerga esse
schema. Detalhes em [docs/arquitetura.md](docs/arquitetura.md#isolamento-entre-salões-história-2).
Tudo pela CLI (no Docker: `docker compose exec api python -m app.cli ...`):

| Comando | O que faz |
|---|---|
| `db init` | Cria/atualiza o papel da aplicação e aplica as migrações do `public`. Pode rodar sempre. |
| `tenants create --slug studio-ana --name "Studio Ana" --country BR --owner-email ana@x.com --owner-name Ana` | Cria schema, papel, tabelas, o usuário dono e os dados iniciais da vertical. Mostra a **senha provisória uma única vez**. Se algo falhar no meio, desfaz tudo. Leva poucos segundos (o teste exige menos de 1 minuto). |
| `tenants create ... --plan whatsapp_api` | Plano do salão: `base` (padrão) ou `whatsapp_api` (adicional do WhatsApp automático, V2) |
| `tenants create ... --dsn-ref TENANT_DSN_STUDIO_ANA` | O mesmo, mas em **banco dedicado** (conexões nas variáveis `TENANT_DSN_STUDIO_ANA` e `..._ADMIN`) |
| `tenants migrate --all` | Migra todos os salões, um por vez. Se um falhar, segue para os outros e termina com código 1. |
| `tenants migrate --slug studio-ana` | Migra só um salão |
| `tenants list` | Lista os salões, o status e a versão do banco de cada um |
| `tenants seed-demo` | Cria os salões de demonstração (recusado em produção) |

Padrões por país: BR → `pt-BR`, `America/Sao_Paulo`, `BRL`; PY → `es`, `America/Asuncion`, `PYG`.

### Criando uma migração

```bash
cd backend
uv run alembic -n public revision --autogenerate -m "descricao"                         # tabelas de controle
uv run alembic -n tenant -x schema=t_studio_bella revision --autogenerate \
    --version-path migrations/tenant/core -m "descricao"   # tabelas genéricas (ou .../salon)
```

Migrações de salão precisam funcionar com o código da versão anterior (primeiro adicionar, só depois
remover), porque durante o `migrate --all` há salões em versões diferentes.

## Testes e verificações

```bash
# back-end
cd backend
# testes com Postgres (isolamento entre salões etc.): aponte para um SUPERUSUÁRIO de um servidor
# sem dados reais. Os testes criam e apagam os bancos spbella_test*. Com o compose rodando:
export TEST_ADMIN_DATABASE_URL=postgresql+psycopg://spbella:troque-esta-senha@localhost:5432/postgres
uv run pytest                     # sem a variável, os testes com banco são pulados (no CI, falham)
uv run ruff check . && uv run ruff format --check .

# front-end
cd frontend
npm test                          # testes de tela (Vitest + Testing Library)
npm run typecheck
npm run check:api                 # tipos TypeScript em dia com o openapi.json
npm run check:i18n                # pt-BR.json e es.json com as mesmas chaves
npm run build
```

O CI ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) roda tudo isso, com Postgres real.

## Mudou uma rota da API?

```bash
cd backend && uv run python -m scripts.export_openapi     # atualiza docs/api/openapi.json
cd ../frontend && npm run gen:api                         # atualiza os tipos do front
```

Depois, atualize o [guia](docs/api/README.md) se mudou alguma convenção e registre no
[changelog](docs/api/CHANGELOG.md).

## Regras do projeto

- **Textos para o usuário** (o teste `frontend/src/i18n-coverage.test.ts` falha se houver texto
  escrito direto numa tela ou chave sem tradução) ficam só em `frontend/src/core/i18n/locales/` (textos neutros) e `frontend/src/salon/locales/` (vocabulário do salão), sempre em `pt-BR.json` e `es.json`.
  A API devolve códigos (`error.code`), nunca frases para o usuário.
- **Sem dados pessoais nos logs.** Registre IDs, não nomes, telefones ou e-mails.
- **Nenhum segredo no repositório.** Só `.env.example`.
- **Datas em UTC** no banco e na API. **Dinheiro em inteiro** (`*_minor`).
- Permissões são **sempre** verificadas no back-end: toda rota de salão usa
  `require_permission(Permission.X)` e declara `openapi_extra=permission_doc(Permission.X)`
  (`backend/app/core/accounts/`). O front só esconde botões. O teste `test_permissions.py`
  falha se uma rota nova esquecer disso.
- Todo formulário público usa Turnstile e limite de tentativas.

## Status

Backlog no formato SAL ([docs/backlog.md](docs/backlog.md)). SAL-01 a SAL-03 concluídas (os
serviços de exemplo do SAL-01 chegam com SAL-05). Próxima: SAL-04 (auditoria e consentimento). Ver [backlog](docs/backlog.md).
