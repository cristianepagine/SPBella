# SPBella

Sistema de agendamento para salões de beleza e estética, feito pela **Spartacus Soluções**.
Usado no celular, em português (Brasil) e espanhol (Paraguai).

## Estrutura

| Pasta | O que é |
|---|---|
| [`backend/`](backend/) | API em Python 3.12 + FastAPI + SQLAlchemy 2 + Postgres |
| [`frontend/`](frontend/) | App React + TypeScript + Vite + Tailwind (PWA) |
| [`docs/api/`](docs/api/) | **Documentação da API**: guia, `openapi.json` e changelog |
| [`docs/arquitetura.md`](docs/arquitetura.md) | Decisões de arquitetura e pontos legais |
| [`docs/backlog.md`](docs/backlog.md) | Histórias do MVP e o que fica para depois |

## Pré-requisitos

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Postgres e API)
- [uv](https://docs.astral.sh/uv/) para o back-end (`pip install uv`). Ele instala o Python 3.12 sozinho.
- Node.js 24 para o front-end

## Rodando em desenvolvimento

```bash
cp .env.example .env              # e troque POSTGRES_PASSWORD
docker compose up --build         # Postgres + API em http://localhost:8000

cd frontend
cp .env.example .env
npm install
npm run dev                       # app em http://localhost:5173
```

- Documentação interativa da API: <http://localhost:8000/docs> (Swagger) e <http://localhost:8000/redoc>.
- A API recarrega sozinha quando um arquivo em `backend/app/` é salvo.

### Back-end sem Docker

```bash
cd backend
uv sync --python 3.12
uv run uvicorn app.main:app --reload     # precisa de um Postgres; ajuste DATABASE_URL no .env
```

## Testes e verificações

```bash
# back-end
cd backend
uv run pytest                     # testes (inclui: openapi.json em dia e toda rota documentada)
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

- **Textos para o usuário** ficam só em `frontend/src/i18n/locales/` (`pt-BR.json` e `es.json`).
  A API devolve códigos (`error.code`), nunca frases para o usuário.
- **Sem dados pessoais nos logs.** Registre IDs, não nomes, telefones ou e-mails.
- **Nenhum segredo no repositório.** Só `.env.example`.
- **Datas em UTC** no banco e na API. **Dinheiro em inteiro** (`*_minor`).
- Permissões são **sempre** verificadas no back-end.

## Status

História 1 (esqueleto) concluída. Próxima: história 2 (multitenancy). Ver [backlog](docs/backlog.md).
