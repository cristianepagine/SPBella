"""Configuração lida de variáveis de ambiente (ver .env.example na raiz)."""

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    # Procura o .env na raiz do repositório e, se existir, um em backend/ (tem prioridade).
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    app_env: Literal["development", "test", "production"] = "development"
    app_version: str = "0.1.0"

    database_url: str = Field(
        default="postgresql+psycopg://spbella:spbella@localhost:5432/spbella",
        description="Conexão do banco principal (schema public + tenants compartilhados).",
    )

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
