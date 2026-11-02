# Changelog da API

Mudanças visíveis para quem consome a API. Formato: [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).

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
