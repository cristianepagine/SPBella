"""Formato padrão de erro da API.

Toda resposta de erro tem este formato (documentado em docs/api/README.md):

    {"error": {"code": "not_found", "message": "...", "request_id": "...", "fields": [...]}}

- `code` é estável e é o que o front traduz (arquivos pt-BR.json / es.json).
- `message` é só para desenvolvedores; nunca é mostrado ao usuário final.
- `fields` aparece apenas em erros de validação (422).
"""

from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import log

_STATUS_CODES = {
    400: "bad_request",
    401: "not_authenticated",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    422: "validation_error",
    429: "too_many_requests",
    503: "service_unavailable",
}


class FieldError(BaseModel):
    field: str
    code: str


class ErrorBody(BaseModel):
    code: str
    message: str
    request_id: str | None = None
    fields: list[FieldError] | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody


class ApiError(Exception):
    """Erro de negócio com código próprio, ex.: ApiError(409, "slot_taken")."""

    def __init__(self, status_code: int, code: str, message: str | None = None) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message or HTTPStatus(status_code).phrase


def error_responses(*status_codes: int) -> dict[int | str, dict[str, Any]]:
    """Atalho para documentar erros nas rotas: responses=error_responses(404, 409)."""
    return {
        code: {"model": ErrorResponse, "description": HTTPStatus(code).phrase}
        for code in status_codes
    }


def _body(request: Request, status_code: int, code: str, message: str, fields=None) -> JSONResponse:
    error = ErrorBody(
        code=code,
        message=message,
        request_id=getattr(request.state, "request_id", None),
        fields=fields,
    )
    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse(error=error).model_dump(exclude_none=True),
    )


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(request: Request, exc: ApiError) -> JSONResponse:
        return _body(request, exc.status_code, exc.code, exc.message)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _STATUS_CODES.get(exc.status_code, "error")
        message = exc.detail if isinstance(exc.detail, str) else HTTPStatus(exc.status_code).phrase
        return _body(request, exc.status_code, code, message)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Não devolvemos o valor enviado (pode conter dado pessoal), só o campo e o tipo do erro.
        fields = [
            FieldError(field=".".join(str(p) for p in e["loc"] if p != "body"), code=e["type"])
            for e in exc.errors()
        ]
        return _body(request, 422, "validation_error", "Dados inválidos", fields)

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, exc: Exception) -> JSONResponse:
        log.error("unexpected_error", error_type=type(exc).__name__, path=request.url.path)
        return _body(request, 500, "internal_error", "Erro interno")
