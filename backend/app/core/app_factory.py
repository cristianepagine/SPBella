"""Monta a aplicação FastAPI: infraestrutura e rotas do core + rotas da vertical."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.accounts import api as accounts_api
from app.core.accounts import team_api
from app.core.infra.config import Settings
from app.core.infra.db import Databases
from app.core.infra.errors import register_error_handlers
from app.core.infra.logging import configure_logging
from app.core.infra.mailer import build_mailer
from app.core.infra.middleware import REQUEST_ID_HEADER, RequestContextMiddleware
from app.core.infra.ratelimit import RateLimiter
from app.core.infra.turnstile import build_turnstile
from app.core.system import api as system_api
from app.core.tenants import api as tenants_api
from app.core.vertical import Vertical

CORE_OPENAPI_TAGS = [
    {"name": "Saúde do sistema", "description": "Verificações usadas por monitoramento e deploy."},
    {
        "name": "Estabelecimento",
        "description": "Dados públicos do estabelecimento (no SPBella, o salão), identificado "
        "pelo `slug` na URL.",
    },
    {
        "name": "Login",
        "description": "Entrar, sair, renovar a sessão e trocar ou redefinir a senha.",
    },
    {
        "name": "Equipe",
        "description": "Quem tem acesso ao sistema e com qual perfil (só o dono).",
    },
]


def build_app(settings: Settings, vertical: Vertical) -> FastAPI:
    configure_logging(settings.log_level)
    databases = Databases(settings)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        yield
        databases.dispose()

    app = FastAPI(
        lifespan=lifespan,
        title=vertical.api_title,
        version=settings.app_version,
        description=vertical.api_description,
        openapi_tags=[*CORE_OPENAPI_TAGS, *vertical.openapi_tags],
        docs_url="/docs" if settings.api_docs_enabled else None,
        redoc_url="/redoc" if settings.api_docs_enabled else None,
        openapi_url="/openapi.json" if settings.api_docs_enabled else None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,  # necessário para o cookie de refresh
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", REQUEST_ID_HEADER],
        expose_headers=[REQUEST_ID_HEADER],
    )
    app.add_middleware(RequestContextMiddleware)

    app.state.settings = settings
    app.state.databases = databases
    app.state.vertical = vertical
    app.state.rate_limiter = RateLimiter(enabled=settings.rate_limit_enabled)
    app.state.turnstile = build_turnstile(settings)
    app.state.mailer = build_mailer(settings)

    register_error_handlers(app)
    app.include_router(system_api.router)
    app.include_router(tenants_api.router)
    app.include_router(accounts_api.router)
    app.include_router(team_api.router)
    for router in vertical.routers:
        app.include_router(router)
    return app
