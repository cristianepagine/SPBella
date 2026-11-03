# Guia da API do SPBella

Este guia é para quem vai consumir a API: o nosso front-end e, no futuro, integrações.
A referência completa de cada endpoint (campos, tipos e exemplos) fica no
[`openapi.json`](openapi.json), gerado a partir do código.

| Onde | O que tem |
|---|---|
| [`openapi.json`](openapi.json) | Especificação OpenAPI 3.1 completa. É a fonte da verdade. |
| `http://localhost:8000/docs` | Swagger interativo (só em desenvolvimento) |
| `http://localhost:8000/redoc` | ReDoc, mais fácil de ler (só em desenvolvimento) |
| [`CHANGELOG.md`](CHANGELOG.md) | O que mudou na API em cada versão |

## Regras da documentação

- **Toda rota tem `summary`, `description` e `tag`.** Um teste (`backend/tests/test_openapi.py`)
  falha se alguma rota estiver sem isso.
- **Todo erro possível da rota é declarado** com `responses=error_responses(...)`.
- **O `openapi.json` salvo precisa estar em dia com o código.** O CI falha se não estiver.
  Depois de mudar qualquer rota, rode:

  ```bash
  cd backend && uv run python -m scripts.export_openapi
  cd ../frontend && npm run gen:api   # atualiza os tipos TypeScript do front
  ```

- Toda mudança visível para quem consome a API entra no [`CHANGELOG.md`](CHANGELOG.md).

## Endereços

| Ambiente | Base da API |
|---|---|
| Desenvolvimento | `http://localhost:8000` |
| Produção | `https://api.<dominio>` (domínio ainda não definido) |

### Salão na URL (`/t/{slug}`)

Toda rota de um salão fica em `/t/{slug}/...`, onde `slug` é o identificador do salão na URL
(ex.: `/t/studio-ana/appointments`). As rotas de saúde (`/health`) não pertencem a nenhum salão.

- O `slug` tem de 3 a 40 caracteres: letras minúsculas, números e hífen (`studio-ana`, `salon-2`).
- Se o salão não existe, está suspenso, ou o slug é malformado, **toda** rota em `/t/{slug}`
  responde `404` com `code: "tenant_not_found"`. A resposta é a mesma nos três casos, para não
  revelar quais salões existem.
- O salão é verificado **antes** de qualquer outra coisa: mesmo um pedido com corpo inválido para um
  salão inexistente recebe `tenant_not_found`, e não `validation_error`.
- Uma rota de um salão **nunca** devolve dados de outro. Buscar pelo ID um registro de outro salão
  responde `404 not_found`, como se o registro não existisse.

## Convenções

### Formato
- Pedidos e respostas em JSON (`Content-Type: application/json`), em UTF-8.
- Nomes de campos em inglês e `snake_case` (`starts_at`, `price_minor`).

### Datas e horas
- Sempre em **UTC**, no formato ISO 8601 com `Z`: `2026-11-03T13:30:00Z`.
- Quem converte para o fuso do salão é o front, usando o `timezone` do salão (ex.: `America/Sao_Paulo`,
  `America/Asuncion`).
- Exceção: horários de trabalho semanais (`"09:00"`) são em hora local do salão, porque não são instantes.

### Valores em dinheiro
- Sempre **número inteiro na menor unidade da moeda**, em campos terminados em `_minor`:
  - BRL: centavos → `R$ 45,90` = `4590`
  - PYG: o guarani não tem centavos → `₲ 150.000` = `150000`
- A moeda é a do salão (`currency`: `BRL` ou `PYG`). Nunca use número com casas decimais.

### Identificadores
- UUID (texto), ex.: `"7f1c2a4e-8d3b-4c1a-9f0e-2b6d5a7c9e11"`.

### Rastreio de pedidos (`X-Request-ID`)
- Toda resposta traz o cabeçalho `X-Request-ID`. O mesmo valor vai nos logs do servidor.
- O cliente pode enviar o próprio `X-Request-ID` (8 a 64 caracteres: letras, números e `-`);
  se for inválido, o servidor gera outro.
- Quando um usuário relatar um problema, peça esse código: ele aparece também no corpo dos erros.

## Erros

Toda resposta de erro tem o mesmo formato:

```json
{
  "error": {
    "code": "validation_error",
    "message": "Dados inválidos",
    "request_id": "0b9f6a52-3c1e-4d7a-9a51-6f0e2d8c4b13",
    "fields": [{ "field": "phone", "code": "string_too_short" }]
  }
}
```

| Campo | Significado |
|---|---|
| `code` | Código estável. **É isso que o front usa** para mostrar a mensagem traduzida (`errors.<code>` em `pt-BR.json` / `es.json`). |
| `message` | Texto técnico para desenvolvedores. **Nunca mostre ao usuário final.** |
| `request_id` | O mesmo do cabeçalho `X-Request-ID`. |
| `fields` | Só em `422`: quais campos estão errados e por quê. O valor enviado **não** é devolvido (pode ser dado pessoal). |

### Códigos gerais

| HTTP | `code` | Quando acontece |
|---|---|---|
| 400 | `bad_request` | Pedido malformado |
| 401 | `not_authenticated` | Sem login ou sessão expirada |
| 403 | `forbidden` | Logado, mas o perfil não tem permissão |
| 404 | `not_found` | Não existe, **ou pertence a outro salão** (nunca revelamos qual dos dois) |
| 404 | `tenant_not_found` | O salão do `slug` não existe, está suspenso ou o slug é inválido |
| 405 | `method_not_allowed` | Método HTTP não suportado na rota |
| 409 | `conflict` | Conflito de estado (cada rota pode ter códigos próprios, ex.: `slot_taken`) |
| 422 | `validation_error` | Campos inválidos (ver `fields`) |
| 429 | `too_many_requests` | Limite de tentativas atingido; tente após o tempo do cabeçalho `Retry-After` |
| 500 | `internal_error` | Erro inesperado; detalhes só no log do servidor |
| 503 | `service_unavailable` / `database_unavailable` | Sistema ou banco fora do ar |

Códigos específicos de negócio são listados na descrição de cada rota no `openapi.json`.

### Códigos de login e permissão

| HTTP | `code` | Quando acontece | O que o app faz |
|---|---|---|---|
| 400 | `turnstile_failed` | Verificação anti-robô falhou | Pede um token novo ao widget e deixa tentar de novo |
| 400 | `wrong_current_password` | Senha atual errada em `/change-password` | Mostra o erro no campo |
| 400 | `invalid_reset_token` | Link de "esqueci a senha" vencido, usado ou de outro salão | Oferece pedir outro link |
| 401 | `invalid_credentials` | E-mail ou senha errados, ou conta desativada (mesma resposta para os três) | Mostra "E-mail ou senha incorretos" |
| 401 | `not_authenticated` | Sem `Authorization`, token vencido, adulterado ou de outro salão | Chama `/refresh` uma vez e repete o pedido |
| 401 | `refresh_invalid` | Sessão encerrada ou vencida | Volta para o login |
| 401 | `refresh_superseded` | Outra aba acabou de renovar a sessão | Tenta `/refresh` de novo uma vez |
| 403 | `forbidden` | O perfil não tem permissão para a ação | Mostra aviso; não tenta de novo |
| 409 | `email_taken` | Já existe alguém com esse e-mail na equipe | Mostra o erro no campo |
| 409 | `cannot_change_self` | Tentou mudar o próprio perfil ou se desativar | Mostra o aviso |
| 409 | `last_owner` | A mudança deixaria o salão sem nenhum dono ativo | Mostra o aviso |
| 403 | `password_change_required` | Senha provisória ainda não trocada | Leva à troca de senha |
| 403 | `forbidden_origin` | Pedido com `Origin` que não é o do app | — |
| 422 | `weak_password` | Senha nova fraca; o motivo está em `fields[0].code` | Mostra o motivo |
| 429 | `too_many_requests` | Tentativas demais; espere o tempo do cabeçalho `Retry-After` (segundos) | Pede para aguardar |

## Autenticação

### Como funciona

1. **Login:** `POST /t/{slug}/auth/login` devolve um `access_token` e grava um cookie `httpOnly`
   (`spbella_refresh`), restrito ao caminho `/t/{slug}/auth`.
2. **Pedidos autenticados:** cabeçalho `Authorization: Bearer <access_token>`. O token vale
   **15 minutos** (`expires_in`) e **só para o salão em que foi emitido**.
3. **Token vencido:** a rota responde `401 not_authenticated`. O app chama
   `POST /t/{slug}/auth/refresh` (o navegador envia o cookie sozinho) e recebe um access token
   novo e um cookie novo. Cada cookie de refresh serve **uma vez**.
4. **Sair:** `POST /t/{slug}/auth/logout`.

Regras para o app (o front já segue todas):
- Guarde o access token **só na memória**. Nunca em `localStorage` nem em `sessionStorage`.
- Toda chamada à API usa `credentials: "include"`, para o navegador enviar e receber o cookie.
- Ao abrir o app, chame `/refresh` para recuperar a sessão sem pedir a senha de novo.
- Se várias chamadas recebem 401 ao mesmo tempo, faça **um só** `/refresh` e reaproveite o resultado.

### Perfis e permissões

As rotas exigem uma **permissão**, e cada perfil tem um conjunto fixo de permissões. A matriz
fica em `backend/app/core/accounts/permissions.py` e é a fonte única de verdade:

| Permissão | O que libera | Dono | Recepção | Profissional |
|---|---|:-:|:-:|:-:|
| `team.manage` | Cadastrar e desativar a equipe | ✅ | | |
| `settings.manage` | Configurações do salão (SAL-03) | ✅ | | |
| `audit.view` | Ver quem alterou dados de clientes (SAL-04) | ✅ | | |
| `catalog.view` | Ver a lista de serviços (para agendar) | ✅ | ✅ | ✅ |
| `catalog.manage` | Cadastrar serviços e preços | ✅ | | |
| `providers.manage` | Profissionais, jornadas, serviços de cada um e folgas | ✅ | | |
| `customers.manage` | Cadastrar e buscar clientes (SAL-07) | ✅ | ✅ | |
| `agenda.view_all` | Agenda de todos os profissionais (SAL-08) | ✅ | ✅ | |
| `agenda.view_own` | A própria agenda (SAL-08) | ✅ | ✅ | ✅ |
| `agenda.manage` | Criar, mover, cancelar, marcar falta (SAL-09) | ✅ | ✅ | |
| `time_off.manage` | Bloqueios: almoço, férias, feriado (SAL-10) | ✅ | | |
| `reports.view` | Relatórios e Excel (SAL-16) | ✅ | | |

- O perfil é lido do banco **a cada pedido**. Mudar o perfil de alguém vale no pedido seguinte,
  mesmo com o token antigo.
- `user.permissions` (no login e em `/me`) é a lista de permissões da pessoa. O app usa essa
  lista para montar o menu, e o servidor confere de novo em cada rota.
- Cada rota protegida traz no `openapi.json` os campos `x-required-permission` (a permissão) e
  `x-allowed-roles` (os perfis que a têm). Sem a permissão: `403 forbidden`.
- Um teste (`backend/tests/test_permissions.py`) percorre **todas** as rotas de salão com os três
  perfis e confirma o 403. Uma rota nova sem permissão declarada faz o teste falhar.

### Senha provisória

Contas criadas pela CLI recebem uma senha provisória e `must_change_password: true`. Até a troca,
só funcionam `GET /me`, `POST /change-password` e `POST /logout`; o resto responde
`403 password_change_required`.

### Regras de senha

De 8 a 128 caracteres, com pelo menos 4 caracteres diferentes, sem conter a parte do e-mail antes do
`@` e diferente da atual. O motivo da recusa vem em `fields[0].code`: `too_short`, `too_long`,
`too_simple`, `contains_email` ou `same_as_current`.

## Formulários públicos: Turnstile e limite de tentativas

Login, "esqueci a senha" e "criar senha nova" exigem o campo `turnstile_token`, com o token do
widget [Cloudflare Turnstile](https://developers.cloudflare.com/turnstile/). Cada token vale uma
vez: depois de um erro, o app pede outro ao widget. Em desenvolvimento, sem a chave secreta
configurada, a verificação é pulada (em produção, isso é proibido).

| Rota | Limite |
|---|---|
| `/auth/login` | 10 por conta a cada 15 min; 20 por IP por minuto |
| `/auth/forgot-password` | 3 por e-mail e 5 por IP a cada 15 min |
| `/auth/reset-password` | 10 por IP a cada 15 min |
| `/auth/change-password` | 10 por pessoa a cada 15 min |

Passou do limite: `429 too_many_requests` com o cabeçalho `Retry-After` (segundos).

## Endpoints

### Saúde do sistema

#### `GET /health` — a API está no ar?

Não acessa o banco e não exige login. Usado pelo healthcheck do Docker e pelo monitor de disponibilidade.

```bash
curl -i http://localhost:8000/health
```

```http
HTTP/1.1 200 OK
X-Request-ID: 3f2b8c1e-...

{"status": "ok", "version": "0.1.0"}
```

#### `GET /health/ready` — a API está pronta para atender?

Executa `SELECT 1` no Postgres (espera no máximo 3 segundos). Não exige login.

```bash
curl -i http://localhost:8000/health/ready
```

| HTTP | Corpo |
|---|---|
| 200 | `{"status": "ok", "database": "ok"}` |
| 503 | `{"error": {"code": "database_unavailable", ...}}` |

### Salão

#### `GET /t/{slug}` — dados públicos do salão

Nome, país, idioma, fuso e moeda do salão. O app e a página de agendamento usam isso para se
apresentar e para formatar datas (`timezone`) e valores (`currency`). Não exige login e **não traz
dados pessoais**.

```bash
curl -i http://localhost:8000/t/studio-bella
```

```http
HTTP/1.1 200 OK

{
  "slug": "studio-bella",
  "name": "Studio Bella (demonstração)",
  "country": "BR",
  "locale": "pt-BR",
  "timezone": "America/Sao_Paulo",
  "currency": "BRL"
}
```

| Campo | Valores |
|---|---|
| `country` | `BR` ou `PY` |
| `locale` | `pt-BR` ou `es`: idioma padrão do salão. O app usa esse idioma se a pessoa nunca escolheu outro. |
| `timezone` | Fuso IANA, ex.: `America/Sao_Paulo`, `America/Asuncion` |
| `currency` | `BRL` ou `PYG`: moeda de todos os campos `*_minor` desse salão |

| HTTP | Quando |
|---|---|
| 200 | Salão ativo |
| 404 `tenant_not_found` | Salão inexistente, suspenso ou slug inválido |

### Login

Detalhes de cada campo e de cada erro estão no `openapi.json` (tag **Login**). Exemplos com o
salão de demonstração (`tenants seed-demo`):

#### `POST /t/{slug}/auth/login` — entrar

```bash
curl -i -c cookies.txt -X POST http://localhost:8000/t/studio-bella/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email": "dono@studio-bella.demo", "password": "demo-spbella", "turnstile_token": "..."}'
```

```http
HTTP/1.1 200 OK
Set-Cookie: spbella_refresh=...; HttpOnly; Max-Age=2592000; Path=/t/studio-bella/auth; SameSite=strict; Secure

{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 900,
  "user": {
    "id": "4be637c3-2749-45fd-afaa-52780a6d9cf5",
    "name": "Ana Demo",
    "email": "dono@studio-bella.demo",
    "role": "owner",
    "must_change_password": false
  }
}
```

#### `GET /t/{slug}/auth/me` — quem sou eu

```bash
curl http://localhost:8000/t/studio-bella/auth/me -H "Authorization: Bearer $TOKEN"
```

Responde com o mesmo objeto `user` do login.

#### `POST /t/{slug}/auth/refresh` — renovar a sessão

```bash
curl -b cookies.txt -c cookies.txt -X POST http://localhost:8000/t/studio-bella/auth/refresh
```

Responde igual ao login (novo `access_token`, novo cookie). Sem corpo no pedido.

#### `POST /t/{slug}/auth/logout` — sair

```bash
curl -b cookies.txt -X POST http://localhost:8000/t/studio-bella/auth/logout   # 204
```

#### `POST /t/{slug}/auth/change-password` — trocar a senha

```bash
curl -X POST http://localhost:8000/t/studio-bella/auth/change-password \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"current_password": "demo-spbella", "new_password": "minha-senha-nova-1"}'
```

Responde com uma sessão nova (igual ao login) e encerra as outras sessões da pessoa.

#### `POST /t/{slug}/auth/forgot-password` — esqueci a senha

```bash
curl -X POST http://localhost:8000/t/studio-bella/auth/forgot-password \
  -H 'Content-Type: application/json' \
  -d '{"email": "dono@studio-bella.demo", "turnstile_token": "..."}'    # sempre 202
```

O e-mail sai no idioma do salão, com o link `<APP_PUBLIC_URL>/{slug}/reset-password#token=...`.

#### `POST /t/{slug}/auth/reset-password` — criar senha nova pelo link

```bash
curl -X POST http://localhost:8000/t/studio-bella/auth/reset-password \
  -H 'Content-Type: application/json' \
  -d '{"token": "<token do link>", "new_password": "minha-senha-nova-1", "turnstile_token": "..."}'
```

Responde 204 e encerra todas as sessões da pessoa.

### Configurações

Só para quem tem `settings.manage` (hoje, o dono).

#### `GET /t/{slug}/settings` — ver

```json
{
  "name": "Studio Bella", "locale": "pt-BR", "timezone": "America/Sao_Paulo",
  "currency": "BRL", "country": "BR",
  "timezone_options": ["America/Sao_Paulo", "America/Bahia", "...", "America/Noronha"]
}
```

`timezone_options` traz os fusos sugeridos para o país; a API aceita qualquer fuso IANA válido.

#### `PATCH /t/{slug}/settings` — mudar

Corpo com qualquer combinação de `name`, `locale` (`pt-BR` ou `es`), `timezone`, `buffer_min`
(intervalo mínimo entre atendimentos: 0 a 120, de 5 em 5) e `slot_step_min` (passo dos horários
livres: 5, 10, 15, 20, 30 ou 60). Vale **na hora** para todo mundo: a página pública
(`GET /t/{slug}`), a agenda e os e-mails.

- **A moeda não muda por aqui.** Os preços são guardados na menor unidade da moeda, então trocar
  BRL por PYG mudaria o valor de todos eles. Campos desconhecidos (`currency`, `slug`, `plan`...)
  são ignorados. Além disso, o próprio banco só deixa a API alterar nome, idioma e fuso.
- Fuso desconhecido: `422 validation_error` com `fields[0].code = invalid_timezone`.

### Minha conta

#### `PATCH /t/{slug}/auth/me` — mudar o meu idioma

```bash
curl -X PATCH http://localhost:8000/t/studio-bella/auth/me -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"locale": "es"}'
```

Responde com o `user` atualizado. `{"locale": null}` volta a usar o idioma padrão do
estabelecimento. O idioma fica salvo na conta: vale em qualquer aparelho e nos e-mails que a
pessoa recebe. Qualquer pessoa logada pode mudar o próprio idioma.

### Idioma: qual vale?

Para mostrar o app, nesta ordem:
1. o idioma da conta (`user.locale`), se a pessoa escolheu um;
2. o escolhido neste aparelho, antes de entrar;
3. o idioma padrão do estabelecimento (`GET /t/{slug}` → `locale`);
4. o idioma do navegador (`es-*` → espanhol; o resto → português).

Números, moeda e datas seguem a convenção do **país** do estabelecimento, no idioma da pessoa
(em um salão paraguaio, o guarani aparece como "Gs. 150.000"). Horários em 24 h, sempre no fuso
do estabelecimento.

### Profissionais

Ver: `agenda.view_own` (todos da equipe). Cadastrar e alterar: `providers.manage` (dono).

```json
{
  "id": "…", "name": "Paula Souza", "color": "sky", "is_active": true,
  "user_id": "…",
  "offering_ids": ["…"],
  "working_hours": [
    {"weekday": 1, "start": "09:00", "end": "12:00"},
    {"weekday": 1, "start": "13:00", "end": "19:00"}
  ]
}
```

- **`weekday`**: 0 = segunda, 1 = terça, …, 6 = domingo (padrão ISO; atenção, o `getDay()` do
  JavaScript começa no domingo).
- **`start` / `end`**: hora **local** do estabelecimento, `HH:MM`, em múltiplos de 5 minutos. Duas
  faixas no mesmo dia = intervalo entre elas (o almoço do exemplo). Dia sem faixa = não trabalha.
  Turno que passa da meia-noite não é suportado.
- **`color`**: uma de `rose`, `violet`, `sky`, `emerald`, `amber`, `orange`, `teal`, `fuchsia`,
  `lime`, `slate`. Sem cor, o sistema escolhe uma ainda não usada.
- **`user_id`**: a conta de acesso da pessoa (de qualquer perfil, inclusive o dono que também
  atende). Uma conta só pode estar ligada a um profissional (`409 user_already_linked`).

| Rota | O que faz |
|---|---|
| `POST /t/{slug}/providers` | Cadastra (`name`, e opcionalmente `color`, `user_id`, `offering_ids`, `working_hours`) |
| `PATCH /t/{slug}/providers/{provider_id}` | Muda `name`, `color`, `is_active`, `user_id` (`null` desliga a conta) |
| `PUT /t/{slug}/providers/{provider_id}/working-hours` | Substitui a semana inteira: `{"ranges": [...]}` |
| `PUT /t/{slug}/providers/{provider_id}/offerings` | Substitui o que a pessoa faz: `{"offering_ids": [...]}` |

#### Folgas e férias

```bash
curl -X POST http://localhost:8000/t/studio-bella/providers/$ID/time-off \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"start_date": "2026-12-24", "end_date": "2026-12-26", "reason": "Natal"}'
```

Dias inteiros, do primeiro ao último **inclusive**, no fuso do estabelecimento. A resposta traz
também os instantes em UTC: `starts_at` = meia-noite local do primeiro dia; `ends_at` =
meia-noite local do dia seguinte ao último. `GET` lista as folgas que ainda não terminaram;
`DELETE /time-off/{time_off_id}` cancela uma folga.

### Agenda

#### `GET /t/{slug}/agenda` — o dia ou a semana

| Parâmetro | |
|---|---|
| `start` | Primeiro dia, **data local** do estabelecimento (`2026-11-03`) |
| `days` | De 1 a 7 (1 = o dia; 7 = a semana) |
| `provider_id` | Opcional: só um profissional (para quem vê todos) |

```json
{
  "start_date": "2026-11-03", "days": 1, "timezone": "America/Sao_Paulo",
  "scope": "all", "own_provider_missing": false,
  "providers": [{"id": "…", "name": "Paula", "color": "sky",
                 "working_hours": [{"weekday": 1, "start": "09:00", "end": "18:00"}]}],
  "appointments": [{
    "id": "…", "provider_id": "…", "offering_id": "…", "offering_name": "Corte feminino",
    "customer_id": "…", "customer_name": "Maria Oliveira",
    "customer_phone_display": "+55 11 98111-0001",
    "starts_at": "2026-11-03T13:00:00Z", "ends_at": "2026-11-03T14:00:00Z",
    "status": "confirmed", "source": "public"
  }],
  "time_off": [{"id": "…", "provider_id": "…", "starts_at": "…", "ends_at": "…", "reason": "Férias"}]
}
```

- O período é calculado no fuso do estabelecimento: um horário às 23:30 de São Paulo
  (02:30 UTC do dia seguinte) aparece no dia em que acontece para o salão. Um agendamento que
  passa da meia-noite aparece nos dois dias.
- **Quem vê o quê:** quem tem `agenda.view_all` (dono, recepção) vê todos os profissionais e o
  telefone do cliente (`scope: "all"`). O profissional (`agenda.view_own`) vê **só** o
  profissional ligado à própria conta, e o cliente **sem telefone** (`scope: "own"`); se a conta
  não estiver ligada, a resposta vem vazia com `own_provider_missing: true`.
- **Status:** `scheduled` (agendado), `confirmed` (confirmado), `completed` (atendido),
  `no_show` (faltou), `cancelled` (cancelado). Todos vêm na agenda; só os dois primeiros
  ocupam o horário.
- **Dupla reserva é impossível:** o banco tem uma constraint de exclusão
  (`btree_gist` + `tstzrange`, intervalo `[início, fim)`) por profissional, só entre agendamentos
  ativos. Um agendamento pode começar exatamente quando o anterior termina.

#### `POST /t/{slug}/appointments` — marcar horário

Quem tem `agenda.manage` (dono e recepção).

```bash
curl -X POST http://localhost:8000/t/studio-bella/appointments -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"provider_id": "…", "offering_id": "…", "customer_id": "…",
       "starts_at": "2026-11-03T13:00:00Z"}'
```

O fim é calculado pela duração do serviço. Horários de 5 em 5 minutos.

| Resposta | Quando |
|---|---|
| `201` | Marcado (`status: "scheduled"`, `source: "staff"`) |
| `409 slot_taken` | O profissional já tem alguém nesse horário. Vale também quando duas pessoas tentam o mesmo horário ao mesmo tempo: só uma consegue |
| `409 outside_working_hours` / `409 provider_time_off` / `409 too_close` | Fora da jornada, em folga/bloqueio, ou sem o intervalo mínimo até outro atendimento. Reenvie com `"allow_outside_hours": true` para um **encaixe** (nunca vale por cima de outro cliente) |
| `409 customer_without_consent` | O cliente retirou a autorização de uso dos dados para atendimento |
| `422 provider_cannot_do` | O profissional não faz esse serviço |
| `422 unknown_provider` / `unknown_offering` / `unknown_customer` | Não existe ou está desativado |
| `422 invalid_time_step` | Minutos fora do passo de 5 |

**Como a dupla reserva é impedida:** antes de conferir o horário, a API trava a linha do
profissional (`SELECT … FOR UPDATE`), então pedidos simultâneos para o mesmo profissional entram em
fila. Se algo escapar, a constraint de exclusão do banco recusa e a resposta continua sendo
`409 slot_taken`.

#### `PATCH /t/{slug}/appointments/{appointment_id}` — mover

Qualquer combinação de `starts_at`, `provider_id` e `offering_id` (o fim é recalculado), mais
`allow_outside_hours`. Mesmos erros de marcar; só agendamentos ativos podem ser movidos
(`409 not_active`). Mover alguns minutos dentro do próprio horário não conflita com ele mesmo.

#### `POST /t/{slug}/appointments/{appointment_id}/status` — confirmar, atendido, faltou, cancelar

`{"status": "confirmed" | "completed" | "no_show" | "cancelled" | "scheduled"}`

- `completed` (atendido) e `no_show` (faltou) só depois do horário de início (`409 too_early`).
- `cancelled` libera o horário na hora.
- Voltar um cancelado para `scheduled` ou `confirmed` só se o horário continuar livre
  (`409 slot_taken`).

### Bloqueios

Só o dono (`time_off.manage`). O almoço de todo dia se faz na jornada do profissional (duas faixas
no dia); bloqueio é para o que é pontual.

#### `POST /t/{slug}/blocks`

| Bloqueio | Corpo |
|---|---|
| Feriado (estabelecimento inteiro) | `{"start_date": "2026-12-25", "reason": "Natal"}` |
| Férias de um profissional | `{"provider_id": "…", "start_date": "2027-01-10", "end_date": "2027-01-20"}` |
| Algumas horas | `{"provider_id": "…", "start_date": "2026-11-05", "start_time": "14:00", "end_time": "16:00", "reason": "Médico"}` |

- `provider_id` vazio = o estabelecimento inteiro.
- Datas e horas são **locais**. Dias inteiros vão de meia-noite a meia-noite; o `end_date` é
  inclusive.
- A resposta (`201`) traz `conflicts`: os agendamentos ativos que já estavam no período. **Nada é
  cancelado sozinho**: a equipe decide se remarca ou cancela.
- Bloqueado não aparece em `/availability` (nem na página pública) e recusa marcações com
  `409 provider_time_off`.
- `422` com `fields[0].code`: `start_and_end_required`, `start_after_end`, `invalid_time_step`,
  `hours_block_is_one_day`, `end_before_start`, `too_long`, `unknown_provider`.

`DELETE /t/{slug}/blocks/{block_id}` remove o bloqueio (os bloqueios aparecem em
`GET /agenda` → `time_off`, com o `id`).

### Horários livres

#### `GET /t/{slug}/availability?offering_id=…&date=AAAA-MM-DD[&provider_id=…]`

Quem tem `agenda.manage`. **Horários livres = jornada − bloqueios − agendamentos ativos**,
respeitando:

- a **duração** do serviço, que precisa caber inteira numa faixa da jornada (não atravessa o
  almoço nem a meia-noite);
- o **intervalo mínimo** entre atendimentos (`buffer_min`, nas Configurações), antes e depois de
  cada agendamento ativo;
- o **passo** dos horários (`slot_step_min`: 9:00, 9:15, 9:30…).

Sem `provider_id`, junta todos os profissionais que fazem o serviço ("sem preferência"):

```json
{"date": "2026-11-03", "timezone": "America/Sao_Paulo", "offering_id": "…", "duration_min": 60,
 "slots": [{"starts_at": "2026-11-03T12:00:00Z", "provider_ids": ["…", "…"]}]}
```

O cálculo segue o fuso do estabelecimento, inclusive em dias de mudança de horário de verão (a
jornada local continua a mesma; os instantes UTC mudam).

### Itens agendáveis

`GET /t/{slug}/offerings` (`catalog.view`): nome e duração de tudo o que pode ser agendado, sem
preço. É a versão genérica (do core) da lista de serviços; no salão, `/services` traz o preço.

### Serviços (vertical salão)

Ver: `catalog.view` (todos os perfis). Cadastrar e alterar: `catalog.manage` (dono).

| Campo | Regra |
|---|---|
| `name` | 1 a 120 caracteres |
| `duration_min` | De 5 a 480 minutos, em múltiplos de 5 (`422 invalid_duration`) |
| `price_minor` | Inteiro na menor unidade da moeda do salão: `8000` = R$ 80,00; `80000` = Gs. 80.000. De 0 a 100.000.000 (`422 invalid_price`) |
| `currency` | Só na resposta: a moeda do salão |
| `is_active` | `false` tira o serviço da agenda e da página pública |

#### `GET /t/{slug}/services` — listar

Ordem alfabética. Só os ativos, a menos que `include_inactive=true`.

```json
[{"id": "…", "name": "Corte feminino", "duration_min": 60, "price_minor": 8000,
  "currency": "BRL", "is_active": true, "updated_at": "…"}]
```

#### `POST /t/{slug}/services` — cadastrar

```bash
curl -X POST http://localhost:8000/t/studio-bella/services -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"name": "Hidratação", "duration_min": 45, "price_minor": 7590}'
```

#### `PATCH /t/{slug}/services/{service_id}` — alterar ou desativar

Qualquer combinação de `name`, `duration_min`, `price_minor` e `is_active`. **Serviços não são
apagados**: agendamentos antigos continuam apontando para eles. Mudar o preço não muda o de
agendamentos já feitos (cada agendamento vai guardar o preço do momento, a partir do SAL-09).

#### Serviços de exemplo

Todo salão criado pelo `tenants create` já nasce com 7 serviços (corte feminino e masculino,
escova, coloração, manicure, pedicure e barba), no idioma e na moeda do salão. O dono ajusta
os preços ou desativa os que não usa.

### Clientes

Para quem tem `customers.manage` (dono e recepção). Toda consulta da ficha, alteração e mudança
de consentimento fica no **log de auditoria**.

#### `POST /t/{slug}/customers` — cadastrar

```bash
curl -X POST http://localhost:8000/t/studio-bella/customers -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"name": "Maria Silva", "phone": "(11) 98888-7777", "email": "maria@exemplo.com",
       "consents": ["service", "reminders"]}'
```

```json
{
  "id": "…", "name": "Maria Silva",
  "phone": "+5511988887777", "phone_display": "+55 11 98888-7777",
  "email": "maria@exemplo.com", "locale": null,
  "created_at": "2026-11-03T13:30:00Z", "updated_at": "2026-11-03T13:30:00Z",
  "consents": [
    {"purpose": "reminders", "granted_at": "…", "source": "staff", "policy_version": "2026-11-02"},
    {"purpose": "service",   "granted_at": "…", "source": "staff", "policy_version": "2026-11-02"}
  ]
}
```

- **Telefone:** aceito como a pessoa digitar. Sem `+DDI`, vale o país do estabelecimento
  (`0981 123456` num salão paraguaio vira `+595981123456`). Sempre devolvido em E.164 (`phone`)
  e formatado para leitura (`phone_display`).
- **Consentimento:** `service` (usar os dados para o atendimento) é **obrigatório**;
  `reminders` (lembretes e confirmações) e `marketing` (novidades) são opcionais. Cada um é
  registrado com a versão da política de privacidade, a origem (`staff` ou `public_booking`) e
  quem registrou.
- `422 validation_error` com `fields[0].code`: `invalid_phone`, `invalid_email` ou
  `consent_required`.

#### `GET /t/{slug}/customers` — listar e buscar

Ordem alfabética, `limit` (até 100) e `offset`. Responde `{"items": [...], "total": 123}`; com
busca, `total` é o número de resultados.

Busca com `q`:

| O que a pessoa digita | Como busca | Exemplo |
|---|---|---|
| Só números e sinais (3+ dígitos) | Em qualquer parte do **telefone** | `98888-77`, `(11) 9888` acham `+5511988887777` |
| Texto | No **nome**, sem acento e sem diferenciar maiúsculas; com várias palavras, o nome precisa ter todas | `joao` acha "João"; `ana sil` acha "Ana Paula Silva" |

```bash
curl -G http://localhost:8000/t/studio-bella/customers -H "Authorization: Bearer $TOKEN" \
  --data-urlencode "q=joao"
```

`%` e `_` são tratados como letras comuns. Com 5 mil clientes, a busca responde em
milissegundos (o teste exige menos de 1 segundo; índices trigram `pg_trgm` aceleram o "contém").

Famílias costumam dividir telefone, então o sistema **não** impede dois clientes com o mesmo
número. O app avisa no cadastro, buscando pelo telefone digitado.

#### `GET /t/{slug}/customers/{customer_id}` — ficha

Gera um registro `customer.viewed` na auditoria. Cliente de outro salão: `404 not_found`.

#### `PATCH /t/{slug}/customers/{customer_id}` — alterar

Só os campos enviados mudam; `"email": null` apaga o e-mail. Enviar um valor igual ao atual
não gera registro na auditoria.

#### `POST /t/{slug}/customers/{customer_id}/consents` — dar ou retirar consentimento

`{"purpose": "marketing", "granted": false}`. O histórico nunca é apagado: retirar preenche a
data de retirada; dar de novo cria um registro novo com a versão atual da política.

### Auditoria

Só para quem tem `audit.view` (hoje, o dono).

#### `GET /t/{slug}/audit` — quem fez o quê

Parâmetros opcionais: `entity_id` (ex.: o ID de um cliente), `before` (paginação: o
`occurred_at` do último registro recebido) e `limit` (até 100). Mais recentes primeiro.

```json
[
  {
    "id": "…", "occurred_at": "2026-11-03T13:31:02.481Z",
    "action": "customer.updated", "entity_type": "customer", "entity_id": "…",
    "actor_type": "user", "actor": {"id": "…", "name": "Rita Recepção"},
    "fields": ["email", "phone"]
  }
]
```

| `action` | Quando |
|---|---|
| `customer.created` | Cliente cadastrado (`fields` = campos preenchidos) |
| `customer.viewed` | Alguém abriu a ficha |
| `customer.updated` | Dados alterados (`fields` = campos que mudaram) |
| `consent.granted` / `consent.revoked` | Consentimento dado ou retirado (`fields` = finalidades) |

- **`fields` traz só os nomes dos campos.** Os valores (nome, telefone, e-mail) nunca vão para a
  auditoria nem para os logs da aplicação.
- **O log só aceita inclusão.** O papel do salão no banco não tem `UPDATE`, `DELETE` nem
  `TRUNCATE` na tabela, e um trigger barra alterações até do administrador.

### Equipe

Só para quem tem `team.manage` (hoje, o dono). Ainda não há envio de e-mail (SAL-14): a senha
provisória volta na resposta **uma única vez**, e o dono a repassa à pessoa.

#### `GET /t/{slug}/team` — listar

```json
[
  {
    "id": "7f1c2a4e-...", "name": "Rita Recepção", "email": "recepcao@studio-bella.demo",
    "role": "reception", "is_active": true, "must_change_password": false,
    "last_login_at": "2026-11-02T13:05:00Z", "created_at": "2026-11-01T10:00:00Z"
  }
]
```

#### `POST /t/{slug}/team` — cadastrar

```bash
curl -X POST http://localhost:8000/t/studio-bella/team -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"name": "Carla Souza", "email": "carla@exemplo.com", "role": "professional"}'
```

```json
{ "member": { "id": "...", "role": "professional", "must_change_password": true, "...": "..." },
  "temporary_password": "Xy7kq2PvA9mN" }
```

#### `PATCH /t/{slug}/team/{member_id}` — alterar

Corpo com qualquer combinação de `name`, `role` e `is_active`. Desativar encerra as sessões da
pessoa na hora. Ninguém muda o próprio perfil nem se desativa (`409 cannot_change_self`), e
precisa sobrar pelo menos um dono ativo (`409 last_owner`).

#### `POST /t/{slug}/team/{member_id}/reset-password` — nova senha provisória

Devolve `{member, temporary_password}`, obriga a troca no próximo login e encerra as sessões.
