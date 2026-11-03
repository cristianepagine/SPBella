"""Configuração lida de variáveis de ambiente (ver .env.example na raiz)."""

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# Só para desenvolvimento e testes. Em produção, JWT_SECRET é obrigatório (ver validador abaixo).
DEV_JWT_SECRET = "dev-only-jwt-secret-nao-use-em-producao-0000"  # noqa: S105 - recusado em produção


class Settings(BaseSettings):
    # Procura o .env na raiz do repositório e, se existir, um em backend/ (tem prioridade).
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    app_env: Literal["development", "test", "production"] = "development"
    app_version: str = "0.9.0"

    # Papel da APLICAÇÃO: sem acesso direto às tabelas dos salões; só entra em um salão
    # com SET LOCAL ROLE (ver app/core/infra/tenancy.py).
    database_url: str = Field(
        default="postgresql+psycopg://spbella_app:spbella_app@localhost:5432/spbella",
        description="Conexão da API com o banco principal (papel da aplicação).",
    )
    # Papel ADMINISTRADOR: cria schemas, papéis e roda migrações. Usado só pela CLI.
    database_admin_url: str | None = None
    db_pool_size: int = 5

    # Prefixo dos papéis do Postgres de cada salão (ex.: spbella_t_studio_ana). Papéis valem
    # para o servidor inteiro, então o prefixo evita colisão entre sistemas no mesmo servidor.
    tenant_role_prefix: str = "spbella_"

    # Lista separada por vírgula. Ex.: https://app.exemplo.com.br,http://localhost:5173
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173"]

    # Swagger (/docs) e ReDoc (/redoc). Em produção ficam desligados.
    api_docs_enabled: bool = True

    log_level: str = "INFO"

    # --- Login ---
    jwt_secret: SecretStr = SecretStr(DEV_JWT_SECRET)
    access_token_minutes: int = 15
    refresh_token_days: int = 30
    # Segundos em que um refresh recém-trocado ainda é aceito como "corrida entre abas"
    # (não derruba a sessão). Depois disso, reapresentar um refresh trocado = roubo.
    refresh_reuse_grace_seconds: int = 30
    password_reset_minutes: int = 30
    # Cookies só por HTTPS. Desligue apenas em testes com cliente HTTP puro.
    cookie_secure: bool = True

    # Versão da política de privacidade aceita nos consentimentos dos clientes (LGPD). Troque
    # quando o texto da política mudar: consentimentos novos passam a registrar a versão nova.
    privacy_policy_version: str = "2026-11-02"

    # Endereço do app (front), usado nos links enviados por e-mail.
    app_public_url: str = "http://localhost:5173"

    # Cloudflare Turnstile. Sem chave, a verificação é pulada (só fora de produção).
    turnstile_secret_key: SecretStr | None = None

    # Atrás do Cloudflare, o IP real vem do cabeçalho CF-Connecting-IP. Só ligue se a API
    # NÃO for acessível sem passar pelo Cloudflare (ex.: Cloudflare Tunnel).
    trust_cloudflare_ip_header: bool = False
    rate_limit_enabled: bool = True

    # console: imprime o e-mail no terminal (só desenvolvimento) | memory: testes |
    # disabled: não envia (o envio real por e-mail entra na história 9).
    mail_backend: Literal["console", "memory", "disabled"] = "console"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [o.strip() for o in value.split(",") if o.strip()]
        return value

    @model_validator(mode="after")
    def _production_requirements(self) -> "Settings":
        if self.app_env != "production":
            return self
        problems = []
        secret = self.jwt_secret.get_secret_value()
        if secret == DEV_JWT_SECRET or len(secret) < 32:
            problems.append("JWT_SECRET com pelo menos 32 caracteres")
        if self.turnstile_secret_key is None:
            problems.append("TURNSTILE_SECRET_KEY")
        if self.mail_backend == "console":
            problems.append("MAIL_BACKEND diferente de console (o console imprime dados pessoais)")
        if not self.cookie_secure:
            problems.append("COOKIE_SECURE=true")
        if problems:
            raise ValueError("configuração de produção incompleta: " + "; ".join(problems))
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
