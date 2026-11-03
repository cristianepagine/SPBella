"""Salões de demonstração (`tenants seed-demo`), para mostrar no primeiro contato com o cliente."""

from sqlalchemy.orm import Session

from app.core.infra.tenancy import TenantContext
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


def seed_demo_salon(session: Session, tenant: TenantContext) -> None:
    """Dados extras da demonstração. Os três profissionais com jornadas chegam no SAL-06."""
