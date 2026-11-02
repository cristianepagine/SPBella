"""Conexões com o banco.

`Databases` guarda um engine por string de conexão. Um salão usa o banco principal, ou um
banco dedicado quando `tenants.dsn_ref` está preenchido: o valor é o NOME de uma variável de
ambiente (ex.: TENANT_DSN_STUDIO_ANA) que contém a conexão. Assim nenhuma senha fica no banco
e mover um cliente para banco próprio é só configuração.

Rotas NUNCA usam estes engines direto: a sessão de um salão sai de app/core/tenancy.py.
"""

import os
import re
import threading

from sqlalchemy import Engine, create_engine, text

from app.core.config import Settings

DSN_REF_PATTERN = re.compile(r"^TENANT_DSN_[A-Z0-9_]{1,40}$")


def resolve_dsn_ref(dsn_ref: str, *, admin: bool = False) -> str:
    """Lê a conexão de um banco dedicado. `admin=True` lê a variável <dsn_ref>_ADMIN."""
    # O padrão impede que um valor adulterado leia outra variável (ex.: DATABASE_ADMIN_URL).
    if not DSN_REF_PATTERN.match(dsn_ref):
        raise ValueError(f"dsn_ref inválido: {dsn_ref!r}")
    name = f"{dsn_ref}_ADMIN" if admin else dsn_ref
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"variável de ambiente {name} não definida")
    return value


class Databases:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._engines: dict[str, Engine] = {}
        self._lock = threading.Lock()

    def engine(self, url: str) -> Engine:
        with self._lock:
            if url not in self._engines:
                self._engines[url] = create_engine(
                    url,
                    pool_pre_ping=True,
                    pool_size=self.settings.db_pool_size,
                    max_overflow=self.settings.db_pool_size,
                    connect_args={"connect_timeout": 3},
                )
            return self._engines[url]

    @property
    def control(self) -> Engine:
        """Banco principal, onde fica public.tenants."""
        return self.engine(self.settings.database_url)

    def for_tenant(self, dsn_ref: str | None) -> Engine:
        return self.engine(resolve_dsn_ref(dsn_ref) if dsn_ref else self.settings.database_url)

    def is_ready(self) -> bool:
        try:
            with self.control.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception:  # noqa: BLE001 - qualquer falha significa "banco indisponível"
            return False

    def dispose(self) -> None:
        with self._lock:
            for engine in self._engines.values():
                engine.dispose()
            self._engines.clear()
