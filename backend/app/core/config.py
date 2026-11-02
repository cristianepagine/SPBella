"""Configuração lida de variáveis de ambiente (ver .env.example na raiz)."""

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    # Procura o .env na raiz do repositório e, se existir, um em backend/ (tem prioridade).
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    app_env: Literal["development", "test", "production"] = "development"
    app_version: str = "0.2.0"

    # Papel da APLICAÇÃO: sem acesso direto às tabelas dos salões; só entra em um salão
    # com SET LOCAL ROLE (ver app/core/tenancy.py).
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

    # Swagger (/docs) e ReDoc (/redoc). Em produção ficam desligados até existir login.
    api_docs_enabled: bool = True

    log_level: str = "INFO"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [o.strip() for o in value.split(",") if o.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
