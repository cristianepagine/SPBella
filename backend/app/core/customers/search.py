"""Normalização para busca: sem acento, sem diferença de maiúsculas, espaços simples.

Feita em Python (e guardada em customers.search_name) para não depender da extensão unaccent
do Postgres. O índice trigram (pg_trgm), quando existe, deixa o "contém" rápido.
"""

import re
import unicodedata


def normalize_text(text: str) -> str:
    """'  JOÃO   da Silva ' → 'joao da silva'."""
    decomposed = unicodedata.normalize("NFKD", text)
    without_accents = "".join(c for c in decomposed if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", without_accents).strip().lower()


def digits(text: str) -> str:
    return re.sub(r"\D", "", text)


def looks_like_phone(query: str) -> bool:
    """Busca por telefone quando a pessoa digita só números e sinais (ex.: '(11) 98888-77')."""
    return bool(re.fullmatch(r"[\d\s()+\-.]+", query)) and len(digits(query)) >= 3


def like_pattern(term: str) -> str:
    """Escapa % e _ para o LIKE e envolve em % (contém)."""
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"
