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
| Fila | Tabela `public.jobs` com `FOR UPDATE SKIP LOCKED` + `LISTEN/NOTIFY` | Sem Redis, custo menor |
| Erros | `{"error": {"code", ...}}`; o front traduz o `code` | Nenhum texto para o usuário fixo no back-end |
| Logs | JSON (structlog), filtro de dados pessoais, sem query string nem corpo | LGPD |
| Hospedagem | VPS em São Paulo, sem portas abertas (Cloudflare Tunnel) | Latência no celular; dados de clientes do BR ficam no Brasil |
| Python | 3.12, dependências gerenciadas com `uv` | Versão pedida; `uv` instala a versão certa sozinho |
| TypeScript | 5.9 (não 7) | O gerador de tipos `openapi-typescript` ainda não roda no TypeScript 7 nativo |
| Datas | UTC no banco; fuso IANA por salão | Brasil e Paraguai sem horário de verão hoje, mas tzdata cobre mudanças futuras |
| Dinheiro | Inteiro na menor unidade (`*_minor`) | Sem erro de arredondamento; PYG não tem centavos |

## Pontos de atenção legais

- **LGPD:** o salão é o **controlador** e a Spartacus é a **operadora** → contrato de operador
  nos termos de uso. Salões pequenos estão dispensados de nomear encarregado (Res. CD/ANPD nº 2/2022),
  mas precisam oferecer um canal de contato ao titular.
- **Paraguai:** aplicamos o padrão da LGPD. A lei geral paraguaia de proteção de dados (2025) tem
  prazo de adequação; **confirmar número, prazos e exigências com advogado local**. Hospedar no
  Brasil é transferência internacional para dados paraguaios. Dados de inadimplência, se um dia
  existirem, seguem também a Ley 6534/2020.
- No código, pontos onde a norma paraguaia pode pedir algo a mais são marcados com `# PY-LEGAL:`.
