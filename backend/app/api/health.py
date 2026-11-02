from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.errors import ApiError, error_responses

router = APIRouter(prefix="/health", tags=["Saúde do sistema"])


class HealthResponse(BaseModel):
    status: Literal["ok"] = Field(description="Sempre `ok` quando a API responde.")
    version: str = Field(description="Versão da API em execução.", examples=["0.1.0"])


class ReadinessResponse(BaseModel):
    status: Literal["ok"]
    database: Literal["ok"] = Field(description="Resultado da verificação do Postgres.")


@router.get(
    "",
    summary="A API está no ar?",
    description=(
        "Verificação de vida (liveness). Não acessa o banco; responde 200 enquanto o processo "
        "estiver de pé. Usada pelo Docker e pelo monitor de disponibilidade. Não exige login."
    ),
    response_model=HealthResponse,
)
def liveness() -> HealthResponse:
    return HealthResponse(status="ok", version=get_settings().app_version)


@router.get(
    "/ready",
    summary="A API está pronta para atender?",
    description=(
        "Verificação de prontidão (readiness). Executa `SELECT 1` no Postgres. "
        "Responde 503 com o código `database_unavailable` se o banco não responder em 3 segundos. "
        "Não exige login."
    ),
    response_model=ReadinessResponse,
    responses=error_responses(503),
)
def readiness(request: Request) -> ReadinessResponse:
    if not request.app.state.databases.is_ready():
        raise ApiError(503, "database_unavailable", "Banco de dados indisponível")
    return ReadinessResponse(status="ok", database="ok")
