"""Salões de demonstração (`tenants seed-demo`), para mostrar no primeiro contato com o cliente.

Cada salão tem um acesso de cada perfil, todos com a senha de demonstração:
dono, recepção e profissional.
"""

from sqlalchemy.orm import Session

from app.core.accounts.models import User
from app.core.infra.security import hash_password
from app.core.infra.tenancy import TenantContext
from app.core.tenants.provisioning import DEMO_PASSWORD
from app.core.vertical import DemoTenant

DEMO_TENANTS = (
    DemoTenant(
        slug="studio-bella",
        name="Studio Bella (demonstração)",
        country="BR",
        owner_email="dono@studio-bella.demo",
        owner_name="Ana Demo",
    ),
    DemoTenant(
        slug="salon-asuncion",
        name="Salón Asunción (demostración)",
        country="PY",
        owner_email="duena@salon-asuncion.demo",
        owner_name="Lucía Demo",
    ),
)

# (perfil, e-mail antes do @, nome) por idioma do salão
DEMO_STAFF = {
    "pt-BR": [
        ("reception", "recepcao", "Rita Recepção"),
        ("professional", "profissional", "Paulo Profissional"),
    ],
    "es": [
        ("reception", "recepcion", "Rosa Recepción"),
        ("professional", "profesional", "Pablo Profesional"),
    ],
}


def seed_demo_salon(session: Session, tenant: TenantContext) -> None:
    """Recepção e profissional de demonstração. Os três profissionais com jornadas: SAL-06."""
    password_hash = hash_password(DEMO_PASSWORD)
    for role, local_part, name in DEMO_STAFF[tenant.locale]:
        session.add(
            User(
                name=name,
                email=f"{local_part}@{tenant.slug}.demo",
                password_hash=password_hash,
                role=role,
                must_change_password=False,
            )
        )
