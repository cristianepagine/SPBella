"""Envio de e-mail.

Por enquanto não há provedor real: o envio por Amazon SES, pela fila, entra na história 9.
- console: imprime no terminal (desenvolvimento). Tem dados pessoais: proibido em produção.
- memory: guarda em uma lista (testes).
- disabled: não envia; registra só que um e-mail deixou de ser enviado.
"""

import sys
from dataclasses import dataclass
from typing import Protocol

from app.core.infra.config import Settings
from app.core.infra.logging import log


@dataclass(frozen=True)
class Email:
    to: str
    subject: str
    body: str


class Mailer(Protocol):
    def send(self, email: Email) -> None: ...


class ConsoleMailer:
    def send(self, email: Email) -> None:
        # print direto (e não o log), para não passar pelo log estruturado com dados pessoais.
        print(
            f"\n--- E-MAIL (desenvolvimento) ---\nPara: {email.to}\nAssunto: {email.subject}\n\n"
            f"{email.body}\n--------------------------------\n",
            file=sys.stderr,
        )


class MemoryMailer:
    def __init__(self) -> None:
        self.outbox: list[Email] = []

    def send(self, email: Email) -> None:
        self.outbox.append(email)


class DisabledMailer:
    def send(self, email: Email) -> None:
        log.warning("email_not_sent", reason="mail_backend_disabled")


def build_mailer(settings: Settings) -> Mailer:
    return {"console": ConsoleMailer, "memory": MemoryMailer, "disabled": DisabledMailer}[
        settings.mail_backend
    ]()
