"""A documentação da API faz parte do código: se mudar uma rota, regenere o openapi.json."""

from app.main import create_app
from scripts.export_openapi import OPENAPI_PATH, render_openapi


def test_saved_openapi_is_up_to_date():
    assert OPENAPI_PATH.exists(), "rode: uv run python -m scripts.export_openapi"
    assert OPENAPI_PATH.read_text(encoding="utf-8") == render_openapi(), (
        "docs/api/openapi.json está desatualizado. Rode: uv run python -m scripts.export_openapi"
    )


def test_every_route_is_documented():
    spec = create_app().openapi()

    for path, operations in spec["paths"].items():
        for method, operation in operations.items():
            where = f"{method.upper()} {path}"
            assert operation.get("summary"), f"{where} sem summary"
            assert operation.get("description"), f"{where} sem description"
            assert operation.get("tags"), f"{where} sem tag"
