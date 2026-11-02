"""Acesso ao banco.

Nesta fase existe só o engine do banco principal. A sessão por tenant
(SET LOCAL ROLE / search_path) entra na história 2 e será o ÚNICO jeito
de as rotas obterem uma sessão.
"""

from functools import lru_cache

from sqlalchemy import Engine, create_engine, text

from app.core.config import get_settings


@lru_cache
def get_engine() -> Engine:
    return create_engine(
        get_settings().database_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
        connect_args={"connect_timeout": 3},
    )


def database_is_ready() -> bool:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001 - qualquer falha significa "banco indisponível"
        return False
