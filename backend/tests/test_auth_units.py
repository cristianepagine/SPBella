"""Partes do login que não precisam de banco."""

import pytest

from app.core.infra.config import Settings
from app.core.infra.ratelimit import RateLimiter, TooManyRequestsError
from app.core.infra.security import hash_token, password_problem
from app.core.infra.turnstile import CloudflareTurnstile, SkipTurnstile, build_turnstile
from tests.conftest import production_settings


@pytest.mark.parametrize(
    ("password", "problem"),
    [
        ("abc123", "too_short"),
        ("x" * 129, "too_long"),
        ("abababab", "too_simple"),
        ("mariasilva2026", "contains_email"),
        ("corte-e-escova-9", None),
    ],
)
def test_password_rules(password, problem):
    assert password_problem(password, "mariasilva@exemplo.com") == problem


def test_rate_limiter_blocks_after_limit_and_reports_retry_after():
    limiter = RateLimiter()
    for _ in range(3):
        limiter.hit("k", limit=3, window_seconds=60)

    with pytest.raises(TooManyRequestsError) as exc_info:
        limiter.hit("k", limit=3, window_seconds=60)

    assert 0 < exc_info.value.retry_after <= 60
    assert exc_info.value.headers == {"Retry-After": str(exc_info.value.retry_after)}
    limiter.hit("outra-chave", limit=3, window_seconds=60)  # chaves são independentes


def test_disabled_rate_limiter_never_blocks():
    limiter = RateLimiter(enabled=False)
    for _ in range(100):
        limiter.hit("k", limit=1, window_seconds=60)


def test_tokens_are_stored_as_hashes():
    assert hash_token("abc") != "abc"
    assert len(hash_token("abc")) == 64


def test_turnstile_is_skipped_only_without_secret():
    assert isinstance(build_turnstile(Settings()), SkipTurnstile)
    assert isinstance(build_turnstile(production_settings()), CloudflareTurnstile)


def test_turnstile_without_token_fails_without_calling_cloudflare():
    assert CloudflareTurnstile("segredo").verify(None, "1.2.3.4") is False


@pytest.mark.parametrize(
    ("override", "missing"),
    [
        ({"jwt_secret": "curto"}, "JWT_SECRET"),
        ({"turnstile_secret_key": None}, "TURNSTILE_SECRET_KEY"),
        ({"mail_backend": "console"}, "MAIL_BACKEND"),
        ({"cookie_secure": False}, "COOKIE_SECURE"),
    ],
)
def test_production_refuses_unsafe_configuration(override, missing):
    with pytest.raises(ValueError, match=missing):
        production_settings(**override)


def test_production_refuses_the_development_jwt_secret():
    from app.core.infra.config import DEV_JWT_SECRET

    with pytest.raises(ValueError, match="JWT_SECRET"):
        production_settings(jwt_secret=DEV_JWT_SECRET)
