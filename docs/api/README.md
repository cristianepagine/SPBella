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

## Autenticação

*Entra na história 3.* Resumo do que virá:
access token curto (15 min) no cabeçalho `Authorization: Bearer <token>`, refresh token em cookie
`httpOnly` restrito a `/t/{slug}/auth`, e o token de um salão não vale em outro.

## Limites de uso e formulários públicos

*Entra nas histórias 3 e 8.* Formulários públicos (agendamento, login, "esqueci a senha") exigem
o token do Cloudflare Turnstile e têm limite de tentativas por IP.

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
