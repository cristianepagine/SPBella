"""Dados iniciais de todo salão novo (rodam dentro do `tenants create`, na mesma transação)."""

from sqlalchemy.orm import Session

from app.core.infra.tenancy import TenantContext
from app.spbella.services.api import add_service

# (nome em pt-BR, nome em es, duração em minutos, preço em BRL, preço em PYG)
SAMPLE_SERVICES = [
    ("Corte feminino", "Corte de dama", 60, 8000, 80_000),
    ("Corte masculino", "Corte de caballero", 30, 4500, 50_000),
    ("Escova", "Brushing", 45, 6000, 60_000),
    ("Coloração", "Coloración", 120, 18000, 200_000),
    ("Manicure", "Manicura", 45, 3500, 40_000),
    ("Pedicure", "Pedicura", 45, 4000, 45_000),
    ("Barba", "Barba", 30, 3500, 35_000),
]


def seed_new_salon(session: Session, tenant: TenantContext) -> None:
    """Serviços de exemplo, no idioma e na moeda do salão. O dono ajusta ou desativa depois."""
    for name_pt, name_es, duration, price_brl, price_pyg in SAMPLE_SERVICES:
        add_service(
            session,
            name=name_es if tenant.locale == "es" else name_pt,
            duration_min=duration,
            price_minor=price_pyg if tenant.currency == "PYG" else price_brl,
        )
