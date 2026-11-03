# Changelog da API

Mudanças visíveis para quem consome a API. Formato: [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).

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
