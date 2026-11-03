# Arquitetura e decisões

Registro das decisões aprovadas na proposta inicial (2026-11-02). Quando uma decisão mudar,
atualize este arquivo dizendo o que mudou e por quê.

## Core e verticais

O código é dividido em **core** (template reutilizável) e **vertical** (`salon`). O core nunca
importa a vertical; ela se pluga pelo objeto `Vertical`. Detalhes e regras em [template.md](template.md).

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

**Como uma sessão entra no salão:** só [app/core/infra/tenancy.py](../backend/app/core/infra/tenancy.py) faz isso. A cada transação ele executa `SET LOCAL ROLE` e `set_config('search_path', ..., true)`. Os dois valem só até o fim da transação, então a conexão volta limpa para o pool. As rotas recebem essa sessão pela dependência `DbSession`, com `scope="function"`: o commit acontece antes de a resposta sair.

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

**Configurações (SAL-03):** o dono edita nome, idioma e fuso, que ficam em `public.tenants`.
O papel da aplicação recebeu `UPDATE` **só nessas três colunas** (`GRANT UPDATE (name, locale,
timezone)`, aplicado pelo `db init`). Slug, status, plano, moeda e os nomes de schema e de papel
continuam bloqueados pelo próprio banco, e um teste prova isso. A alteração passa por uma
única função (`update_tenant_profile`), sempre com o ID do tenant da requisição.

**Auditoria (SAL-04):** `audit_log` em cada schema de tenant, gravado na mesma transação da
mudança (`app/core/audit/service.py`). Só inclusão, por duas barreiras: o papel do tenant perde
`UPDATE`/`DELETE`/`TRUNCATE` (`APPEND_ONLY_TABLES`, reaplicado a cada migração) e um trigger
recusa alterações até do administrador. Guarda nomes de campos, nunca valores. O horário usa
`clock_timestamp()` (e não `now()`) para ordenar registros da mesma transação.

**Busca de clientes (SAL-07):** `customers.search_name` guarda o nome sem acento e em
minúsculas (normalizado em Python, sem depender da extensão `unaccent`). Índices GIN trigram
(`pg_trgm`) no nome e no telefone aceleram o "contém". O `db init` cria a extensão; se o servidor
não tiver, a migração segue sem os índices e a busca continua certa, só sem a aceleração.

**Dupla reserva (SAL-08/09):** `appointments` tem `EXCLUDE USING gist (provider_id WITH =,
tstzrange(starts_at, ends_at, '[)') WITH &&) WHERE status IN ('scheduled', 'confirmed')`. A
extensão `btree_gist` é obrigatória: a migração falha sem ela. Só um Postgres de teste sem
extensões pode seguir, com `ALLOW_MISSING_PG_EXTENSIONS=1`, recusado em produção pelo validador de
configuração. No CI a variável fica desligada, então ali a trava sempre existe e é testada.

**Horários livres (SAL-10/11):** `app/core/scheduling/availability.py` calcula jornada − bloqueios
− agendamentos ativos, com a duração do serviço, o intervalo mínimo (`schedule_settings.buffer_min`)
e o passo (`slot_step_min`). Cada faixa da jornada (hora local) vira instantes UTC pelo fuso do
estabelecimento, então dias de horário de verão funcionam. A equipe usa em `/availability`; a
página pública (SAL-11) vai usar o mesmo cálculo. A marcação pela equipe também respeita o
intervalo mínimo (`409 too_close`, encaixável).

**Mudanças em relação à proposta inicial:**
- A tabela `public.tenant_migrations` não foi criada. A versão de cada salão fica na
  `alembic_version` do próprio schema (`tenants list` mostra), e os erros de migração aparecem na saída de
  `tenants migrate`, que devolve código 1 se algum salão falhar.
- `global_settings` fica para quando houver a primeira configuração global de verdade.
- `public.jobs` entra na história 9 (fila).

## Login (história 3)

| Tema | Decisão |
|---|---|
| Senha | argon2id (`argon2-cffi`); refeito automaticamente no login se os parâmetros ficarem desatualizados |
| Access token | JWT HS256 de 15 min, com `sub` (usuário), `tid` (salão) e `typ`. Algoritmo fixo na leitura (barra `alg: none`). Fica só na memória do app, nunca em `localStorage`. |
| Refresh token | Aleatório (256 bits). No banco, só o hash SHA-256. Vai em cookie `httpOnly`, `SameSite=Strict`, `Secure` (produção), com `Path=/t/{slug}/auth`, então o cookie de um salão nunca é enviado para outro. Vale 30 dias e é renovado a cada uso. |
| Roubo de refresh | Cada uso troca o token. Reapresentar um token já trocado derruba a família inteira (todas as renovações daquele login). Até 30 s depois da troca, tratamos como duas abas renovando ao mesmo tempo: o servidor responde `refresh_superseded` e o app tenta de novo. |
| Perfil | Lido do banco a cada pedido (não do token). Conta desativada perde o acesso no pedido seguinte. |
| Senha provisória | `must_change_password`: até trocar, só `/me`, `/change-password` e `/logout` funcionam (`403 password_change_required` no resto). |
| CSRF | Cookie `SameSite=Strict` mais a checagem de `Origin` nas rotas que mexem no cookie |
| Robôs | Turnstile em login, "esqueci a senha" e redefinição. Limite de tentativas em memória (por IP, por conta). A regra do WAF do Cloudflare é a primeira barreira. |
| Enumeração de contas | Mesma resposta (e o mesmo tempo, via verificação de senha falsa) para e-mail inexistente, senha errada e conta desativada; "esqueci a senha" sempre responde 202 |
| Link de redefinição | Uso único, 30 min, token depois do `#` (não vai para logs nem para o Referer); o app o tira da barra de endereço. Usar o link encerra todas as sessões. |
| Logs | Salão e usuário (IDs) no log de acesso. Nunca e-mail, senha ou token. |

**Limites conhecidos:**
- O limite de tentativas vale por processo. Hoje há um processo só; com mais de um, ele precisa ir para o
  Postgres (está no backlog).
- O e-mail de "esqueci a senha" é enviado durante o pedido. Na história 9 ele passa para a fila,
  com envio real pelo Amazon SES. Até lá, em produção, `MAIL_BACKEND=disabled`: **o link não chega**.
  Por isso, a história 9 precisa vir antes de colocar clientes reais em produção.
- O log de auditoria de logins e trocas de senha (LGPD) entra na história 11. Até lá, ficam os
  eventos `login_succeeded`, `login_failed`, `password_changed` etc. no log da aplicação, sem
  dados pessoais.

## Pontos de atenção legais

- **LGPD:** o salão é o **controlador** e a Spartacus é a **operadora** → contrato de operador
  nos termos de uso. Salões pequenos estão dispensados de nomear encarregado (Res. CD/ANPD nº 2/2022),
  mas precisam oferecer um canal de contato ao titular.
- **Paraguai:** aplicamos o padrão da LGPD. A lei geral paraguaia de proteção de dados (2025) tem
  prazo de adequação; **confirmar número, prazos e exigências com advogado local**. Hospedar no
  Brasil é transferência internacional para dados paraguaios. Dados de inadimplência, se um dia
  existirem, seguem também a Ley 6534/2020.
- No código, pontos onde a norma paraguaia pode pedir algo a mais são marcados com `# PY-LEGAL:`.
