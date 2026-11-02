from fastapi import APIRouter
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.core.config import Settings
from app.core.errors import ApiError
from app.main import create_app


class _Payload(BaseModel):
    email: str
    age: int


def _client_with_test_routes() -> TestClient:
    app = create_app(Settings(app_env="test"))
    router = APIRouter()

    @router.post("/_test/validate")
    def validate(payload: _Payload) -> dict:
        return {}

    @router.get("/_test/conflict")
    def conflict() -> dict:
        raise ApiError(409, "slot_taken")

    @router.get("/_test/boom")
    def boom() -> dict:
        raise RuntimeError("cliente maria@example.com quebrou")

    app.include_router(router)
    return TestClient(app, raise_server_exceptions=False)


def test_not_found_uses_standard_error_format(client):
    response = client.get("/nao-existe")

    assert response.status_code == 404
    body = response.json()["error"]
    assert body["code"] == "not_found"
    assert body["request_id"] == response.headers["X-Request-ID"]


def test_business_error_keeps_its_code():
    response = _client_with_test_routes().get("/_test/conflict")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "slot_taken"


def test_validation_error_lists_fields_without_echoing_values():
    response = _client_with_test_routes().post(
        "/_test/validate", json={"email": "maria@example.com", "age": "abc"}
    )

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert error["fields"] == [{"field": "age", "code": "int_parsing"}]
    assert "maria@example.com" not in response.text
    assert "abc" not in response.text


def test_unexpected_error_hides_details():
    response = _client_with_test_routes().get("/_test/boom")

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"
    assert "maria" not in response.text


def test_request_id_is_generated_and_echoed(client):
    generated = client.get("/health").headers["X-Request-ID"]
    echoed = client.get("/health", headers={"X-Request-ID": "abc12345-ff"}).headers["X-Request-ID"]
    rejected = client.get("/health", headers={"X-Request-ID": "<script>"}).headers["X-Request-ID"]

    assert len(generated) == 36
    assert echoed == "abc12345-ff"
    assert rejected != "<script>"


def test_cors_allows_configured_origin_only(client):
    allowed = client.options(
        "/health",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
    )
    blocked = client.options(
        "/health",
        headers={"Origin": "https://malicioso.example", "Access-Control-Request-Method": "GET"},
    )

    assert allowed.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert "access-control-allow-origin" not in blocked.headers


def test_docs_can_be_disabled():
    client = TestClient(create_app(Settings(app_env="production", api_docs_enabled=False)))

    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404
