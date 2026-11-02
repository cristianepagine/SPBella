"""Gera docs/api/openapi.json a partir do código.

Uso (dentro de backend/):  uv run python -m scripts.export_openapi
O teste tests/test_openapi.py falha se o arquivo salvo estiver desatualizado.
"""

import json
from pathlib import Path

from app.main import create_app

OPENAPI_PATH = Path(__file__).resolve().parents[2] / "docs" / "api" / "openapi.json"


def render_openapi() -> str:
    return json.dumps(create_app().openapi(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main() -> None:
    OPENAPI_PATH.write_text(render_openapi(), encoding="utf-8")
    print(f"OpenAPI salvo em {OPENAPI_PATH}")


if __name__ == "__main__":
    main()
