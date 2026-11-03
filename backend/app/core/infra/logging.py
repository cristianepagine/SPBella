"""Logs em JSON sem dados pessoais.

Duas proteções:
1. Campos com nomes sensíveis (email, telefone, senha, token...) têm o valor substituído.
2. Textos livres passam por um filtro que mascara e-mails, telefones e documentos.

Mesmo assim, a regra é: nunca registre dado pessoal de propósito. Registre IDs.
"""

import logging
import re
import sys
from collections.abc import MutableMapping
from typing import Any

import structlog

REDACTED = "[removido]"

SENSITIVE_KEYS = frozenset(
    {
        "password",
        "senha",
        "contrasena",
        "password_hash",
        "token",
        "access_token",
        "refresh_token",
        "authorization",
        "cookie",
        "set-cookie",
        "email",
        "phone",
        "telefone",
        "telefono",
        "whatsapp",
        "name",
        "nome",
        "nombre",
        "full_name",
        "cpf",
        "cnpj",
        "ruc",
        "ci",
        "documento",
        "document",
        "address",
        "endereco",
        "direccion",
        "birthdate",
    }
)

_PATTERNS = [
    re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),  # e-mail
    re.compile(r"\d{3}\.?\d{3}\.?\d{3}-?\d{2}"),  # CPF
    re.compile(r"\+?\d[\d\s().-]{7,}\d"),  # telefone (BR/PY) e números longos
]


def scrub_text(text: str) -> str:
    for pattern in _PATTERNS:
        text = pattern.sub(REDACTED, text)
    return text


def _scrub(value: Any) -> Any:
    if isinstance(value, str):
        return scrub_text(value)
    if isinstance(value, dict):
        return {
            k: REDACTED if str(k).lower() in SENSITIVE_KEYS else _scrub(v) for k, v in value.items()
        }
    if isinstance(value, list | tuple):
        return [_scrub(v) for v in value]
    return value


# Campos técnicos gerados por nós: não passam pelo filtro de texto (que confundiria datas e IDs
# com telefones). Qualquer campo terminado em "_id" também é considerado seguro.
SAFE_KEYS = frozenset(
    {"timestamp", "level", "request_id", "method", "path", "status", "duration_ms"}
)


def scrub_pii(
    _logger: Any, _method: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    for key in list(event_dict.keys()):
        if key in SAFE_KEYS or key.endswith("_id"):
            continue
        if key.lower() in SENSITIVE_KEYS:
            event_dict[key] = REDACTED
        else:
            event_dict[key] = _scrub(event_dict[key])
    return event_dict


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level)
    # O access log do uvicorn registra a URL completa; o nosso middleware já registra o necessário.
    logging.getLogger("uvicorn.access").disabled = True

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.format_exc_info,
            scrub_pii,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(level)),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False,
    )


log = structlog.get_logger()
