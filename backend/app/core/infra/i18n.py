"""Textos que o BACK-END envia para pessoas (e-mails). Ficam em app/locales/*.json.

A API em si nunca devolve frases para o usuário; devolve códigos que o front traduz.
"""

import json
from functools import lru_cache
from pathlib import Path

LOCALES_DIR = Path(__file__).resolve().parents[1] / "locales"  # app/core/locales
SUPPORTED = ("pt-BR", "es")


@lru_cache
def _catalog(locale: str) -> dict:
    return json.loads((LOCALES_DIR / f"{locale}.json").read_text(encoding="utf-8"))


def translate(locale: str, key: str, **values: object) -> str:
    node: object = _catalog(locale if locale in SUPPORTED else "pt-BR")
    for part in key.split("."):
        node = node[part]  # type: ignore[index]
    return str(node).format(**values)
