# Changelog da API

Mudanças visíveis para quem consome a API. Formato: [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).

## [0.14.0] - 2026-11-03

### Adicionado
- Agendamento online, sem login (tag "Agendamento online"):
  - `GET /t/{slug}/booking/catalog`: serviços (com `extras.price_minor` no salão) e
    profissionais (só nome e cor), mais as regras de antecedência;
  - `GET /t/{slug}/booking/availability`: horários livres já com a antecedência mínima e o
    limite de dias;
  - `POST /t/{slug}/booking`: marca com nome, telefone, e-mail opcional e consentimento
    (`service` obrigatório), Turnstile e limite por IP e por telefone. Códigos novos:
    `409 slot_unavailable`.
- Configurações: `min_notice_min` (antecedência mínima da página pública) e `max_days_ahead`
  (até quantos dias à frente) em `GET/PATCH /t/{slug}/settings`.

## [0.13.0] - 2026-11-03

### Adicionado
- Bloqueios (`time_off.manage`): `POST /t/{slug}/blocks` (dias inteiros ou horas; de um
  profissional ou do estabelecimento) e `DELETE /t/{slug}/blocks/{block_id}`. A resposta traz
  `conflicts` com os agendamentos já marcados no período.
- Horários livres: `GET /t/{slug}/availability?offering_id=&date=[&provider_id=]` (`agenda.manage`).
- Configurações: `buffer_min` (intervalo mínimo entre atendimentos) e `slot_step_min` (passo dos
  horários livres) em `GET/PATCH /t/{slug}/settings`.
- Código `409 too_close` ao marcar sem o intervalo mínimo (dá para encaixar com
  `allow_outside_hours`).

## [0.12.0] - 2026-11-03

### Adicionado
- Agendamentos pela equipe (`agenda.manage`): `POST /t/{slug}/appointments`,
  `PATCH /t/{slug}/appointments/{appointment_id}` (mover) e
  `POST /t/{slug}/appointments/{appointment_id}/status`.
- Códigos: `409 slot_taken`, `outside_working_hours`, `provider_time_off`,
  `customer_without_consent`, `too_early`, `not_active`; `422 provider_cannot_do`,
  `unknown_provider`, `unknown_offering`, `unknown_customer`, `invalid_time_step`.

## [0.11.0] - 2026-11-03

### Adicionado
- Agenda: `GET /t/{slug}/agenda?start=AAAA-MM-DD&days=1..7[&provider_id=]`
  (`agenda.view_own`; quem tem `agenda.view_all` vê todos).
- Agendamentos no banco, com constraint de exclusão contra dupla reserva por profissional.
  Criar e alterar pela API entra na SAL-09.

## [0.10.0] - 2026-11-03

### Adicionado
- Busca de clientes: parâmetro `q` em `GET /t/{slug}/customers` (nome sem acento nem
  maiúsculas, todas as palavras; ou parte do telefone).

## [0.9.0] - 2026-11-03

### Adicionado
- Profissionais: `GET /t/{slug}/providers` (`agenda.view_own`), `POST`, `PATCH /{provider_id}`,
  `PUT /{provider_id}/working-hours`, `PUT /{provider_id}/offerings` (`providers.manage`).
- Folgas: `GET /t/{slug}/providers/{provider_id}/time-off`, `POST` e
  `DELETE /{time_off_id}` (escrever: `providers.manage`).
- Itens agendáveis genéricos: `GET /t/{slug}/offerings` (`catalog.view`).
- Códigos: `409 user_already_linked`; em `422`: `start_after_end`, `overlapping_hours`,
  `invalid_time_step`, `unknown_offering`, `unknown_user`, `end_before_start`, `too_long`.

## [0.8.0] - 2026-11-03

### Adicionado
- Serviços (vertical salão): `GET /t/{slug}/services` (`catalog.view`, todos os perfis),
  `POST /t/{slug}/services` e `PATCH /t/{slug}/services/{service_id}` (`catalog.manage`, dono).
- Permissão `catalog.view` (dono, recepção e profissional).
- Salão novo já vem com 7 serviços de exemplo, no idioma e na moeda do salão.
- Códigos de campo em `422 validation_error`: `invalid_duration`, `invalid_price`.

## [0.7.0] - 2026-11-03

### Adicionado
- Clientes (`customers.manage`): `GET/POST /t/{slug}/customers`,
  `GET/PATCH /t/{slug}/customers/{customer_id}`, `POST /t/{slug}/customers/{customer_id}/consents`.
- Consentimentos por finalidade (`service`, obrigatório; `reminders`; `marketing`), com versão da
  política, origem e quem registrou.
- Auditoria (`audit.view`): `GET /t/{slug}/audit` (filtro `entity_id`, paginação por `before`).
- Códigos de campo em `422 validation_error`: `invalid_phone`, `invalid_email`, `consent_required`.

## [0.6.0] - 2026-11-02

### Adicionado
- Configurações do estabelecimento (`settings.manage`): `GET /t/{slug}/settings` e
  `PATCH /t/{slug}/settings` (nome, idioma padrão, fuso; moeda só leitura; `timezone_options`).
- Idioma de cada pessoa: campo `user.locale` (login, refresh, `/me`) e `PATCH /t/{slug}/auth/me`.
- O e-mail de "esqueci a senha" sai no idioma da pessoa, se ela escolheu um.
- Código de campo `invalid_timezone` em `422 validation_error`.

## [0.5.0] - 2026-11-02

### Adicionado
- `user.permissions` nas respostas de login, refresh, troca de senha e `GET /auth/me`.
- Equipe (só quem tem `team.manage`): `GET /t/{slug}/team`, `POST /t/{slug}/team`,
  `PATCH /t/{slug}/team/{member_id}`, `POST /t/{slug}/team/{member_id}/reset-password`.
- Extensões no `openapi.json`: `x-required-permission` e `x-allowed-roles` em cada rota protegida.
- Códigos de erro: `email_taken`, `cannot_change_self`, `last_owner`.

## [0.4.0] - 2026-11-02

### Alterado
- A tag do OpenAPI de `GET /t/{slug}` passou de "Salão" para "Estabelecimento" (a rota é do
  core, que serve a outros tipos de negócio). Caminhos, campos e respostas **não mudaram**.

## [0.3.0] - 2026-11-02

### Adicionado
- Login: `POST /t/{slug}/auth/login`, `/refresh`, `/logout`, `GET /me`.
- Senha: `POST /t/{slug}/auth/change-password`, `/forgot-password`, `/reset-password`.
- Autenticação `Authorization: Bearer <access_token>` (esquema `HTTPBearer` no OpenAPI).
- Novos códigos de erro: `invalid_credentials`, `not_authenticated`, `refresh_invalid`,
  `refresh_superseded`, `password_change_required`, `forbidden`, `forbidden_origin`,
  `turnstile_failed`, `wrong_current_password`, `weak_password`, `invalid_reset_token`,
  `too_many_requests` (com `Retry-After`).

## [0.2.0] - 2026-11-02

### Adicionado
- `GET /t/{slug}`: dados públicos do salão (nome, país, idioma, fuso, moeda).
- Código de erro `tenant_not_found` (404) para qualquer rota em `/t/{slug}` de salão inexistente,
  suspenso ou com slug inválido.

## [0.1.0] - 2026-11-02

### Adicionado
- `GET /health`: verificação de vida.
- `GET /health/ready`: verificação de prontidão (consulta o Postgres).
- Formato padrão de erro `{"error": {"code", "message", "request_id", "fields"}}`.
- Cabeçalho `X-Request-ID` em todas as respostas.
