"""Ponto de entrada da API (uvicorn app.main:app)."""

from fastapi import FastAPI

from app.core.app_factory import build_app
from app.core.infra.config import Settings, get_settings
from app.registry import VERTICAL


def create_app(settings: Settings | None = None) -> FastAPI:
    return build_app(settings or get_settings(), VERTICAL)


app = create_app()
