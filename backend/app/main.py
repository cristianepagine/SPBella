from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, health, tenants
from app.core.config import Settings, get_settings
from app.core.db import Databases
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging
from app.core.mailer import build_mailer
from app.core.middleware import REQUEST_ID_HEADER, RequestContextMiddleware
from app.core.ratelimit import RateLimiter
from app.core.turnstile import build_turnstile

API_DESCRIPTION = """
API do **SPBella**, sistema de agendamento para salões de beleza e estética.

Guia de uso, convenções (erros, datas, valores, autenticação) e exemplos:
`docs/api/README.md` no repositório.
"""

OPENAPI_TAGS = [
    {"name": "Saúde do sistema", "description": "Verificações usadas por monitoramento e deploy."},
    {"name": "Salão", "description": "Informações de um salão, identificado pelo `slug` na URL."},
    {
        "name": "Login",
        "description": "Entrar, sair, renovar a sessão e trocar ou redefinir a senha.",
    },
]


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)
    databases = Databases(settings)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        yield
        databases.dispose()

    app = FastAPI(
        lifespan=lifespan,
        title="SPBella API",
        version=settings.app_version,
        description=API_DESCRIPTION,
        openapi_tags=OPENAPI_TAGS,
        docs_url="/docs" if settings.api_docs_enabled else None,
        redoc_url="/redoc" if settings.api_docs_enabled else None,
        openapi_url="/openapi.json" if settings.api_docs_enabled else None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,  # necessário para o cookie de refresh (história 3)
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", REQUEST_ID_HEADER],
        expose_headers=[REQUEST_ID_HEADER],
    )
    app.add_middleware(RequestContextMiddleware)

    app.state.settings = settings
    app.state.databases = databases
    app.state.rate_limiter = RateLimiter(enabled=settings.rate_limit_enabled)
    app.state.turnstile = build_turnstile(settings)
    app.state.mailer = build_mailer(settings)

    register_error_handlers(app)
    app.include_router(health.router)
    app.include_router(tenants.router)
    app.include_router(auth.router)
    return app


app = create_app()
