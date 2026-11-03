"""Limite de tentativas em memória (janela deslizante).

Vale por processo da API. Hoje rodamos um processo só; se um dia houver vários, o limite precisa
ir para o Postgres. A regra de rate limit do Cloudflare (WAF) é a primeira barreira; esta é a
segunda, mais fina (por e-mail, por salão).
"""

import math
import threading
import time
from collections import defaultdict, deque

from fastapi import Request

from app.core.infra.config import Settings
from app.core.infra.errors import ApiError


class RateLimiter:
    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key: str, limit: int, window_seconds: int) -> None:
        """Registra uma tentativa; lança 429 se passou do limite na janela."""
        if not self.enabled:
            return
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] <= now - window_seconds:
                hits.popleft()
            if len(hits) >= limit:
                retry_after = math.ceil(hits[0] + window_seconds - now)
                raise TooManyRequestsError(retry_after)
            hits.append(now)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


class TooManyRequestsError(ApiError):
    def __init__(self, retry_after: int) -> None:
        retry_after = max(retry_after, 1)
        super().__init__(
            429, "too_many_requests", "Muitas tentativas", headers={"Retry-After": str(retry_after)}
        )
        self.retry_after = retry_after


def client_ip(request: Request, settings: Settings) -> str:
    if settings.trust_cloudflare_ip_header:
        ip = request.headers.get("CF-Connecting-IP")
        if ip:
            return ip
    return request.client.host if request.client else "desconhecido"
