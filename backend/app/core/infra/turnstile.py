"""Cloudflare Turnstile: prova de que quem enviou o formulário é uma pessoa.

O front coloca o token do widget no campo `turnstile_token`; aqui confirmamos com o Cloudflare.
"""

from typing import Protocol

import httpx

from app.core.infra.config import Settings
from app.core.infra.logging import log

SITEVERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


class TurnstileVerifier(Protocol):
    def verify(self, token: str | None, ip: str) -> bool: ...


class CloudflareTurnstile:
    def __init__(self, secret: str) -> None:
        self._secret = secret

    def verify(self, token: str | None, ip: str) -> bool:
        if not token:
            return False
        try:
            response = httpx.post(
                SITEVERIFY_URL,
                data={"secret": self._secret, "response": token, "remoteip": ip},
                timeout=5,
            )
            return bool(response.json().get("success"))
        except (httpx.HTTPError, ValueError):
            # Sem resposta do Cloudflare, recusamos: melhor pedir para tentar de novo do que
            # deixar o formulário aberto para robôs.
            log.warning("turnstile_unavailable")
            return False


class SkipTurnstile:
    """Usado só em desenvolvimento/testes, quando não há TURNSTILE_SECRET_KEY."""

    def verify(self, token: str | None, ip: str) -> bool:
        return True


def build_turnstile(settings: Settings) -> TurnstileVerifier:
    if settings.turnstile_secret_key is not None:
        return CloudflareTurnstile(settings.turnstile_secret_key.get_secret_value())
    return SkipTurnstile()  # o validador de Settings impede isso em produção
