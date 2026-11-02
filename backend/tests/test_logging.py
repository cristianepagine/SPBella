import json

import structlog

from app.core.logging import REDACTED, configure_logging, scrub_text


def test_sensitive_keys_are_redacted(capsys):
    configure_logging("INFO")
    structlog.get_logger().info(
        "customer_created",
        customer_id="c-123",
        email="maria@example.com",
        telefone="+55 11 98888-7777",
        extra={"password": "segredo", "service": "corte"},
    )

    line = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert line["customer_id"] == "c-123"
    assert line["email"] == REDACTED
    assert line["telefone"] == REDACTED
    assert line["extra"] == {"password": REDACTED, "service": "corte"}


def test_free_text_is_masked():
    text = "falha ao avisar maria@example.com no +595 981 123456, CPF 123.456.789-09"

    masked = scrub_text(text)

    assert "maria@example.com" not in masked
    assert "981 123456" not in masked
    assert "123.456.789-09" not in masked
    assert masked.startswith("falha ao avisar")


def test_access_log_has_no_query_string(client, capsys):
    configure_logging("INFO")
    client.get("/health?email=maria@example.com")

    output = capsys.readouterr().out
    assert '"path": "/health"' in output
    assert "maria" not in output


def test_technical_fields_are_not_mangled(capsys):
    configure_logging("INFO")
    structlog.get_logger().info("job_done", appointment_id="12345678-1234-1234-1234-123456789012")

    line = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert line["appointment_id"] == "12345678-1234-1234-1234-123456789012"
    assert line["timestamp"].startswith("20")
    assert REDACTED not in line["timestamp"]
