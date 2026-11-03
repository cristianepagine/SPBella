"""Salões de demonstração (`tenants seed-demo`), para mostrar no primeiro contato com o cliente.

Cada salão tem um acesso de cada perfil (dono, recepção e profissional), todos com a senha de
demonstração, três profissionais com jornadas e serviços diferentes, seis clientes e uma agenda
de ontem até daqui a 4 dias com todos os status.
"""

import uuid
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.accounts.models import User
from app.core.customers.models import Consent, Customer
from app.core.customers.phones import normalize_phone
from app.core.customers.search import normalize_text
from app.core.infra.security import hash_password
from app.core.infra.tenancy import TenantContext
from app.core.scheduling.models import Appointment, Offering, Provider, WorkingHours
from app.core.tenants.provisioning import DEMO_PASSWORD
from app.core.vertical import DemoTenant
from app.salon.seed import SAMPLE_SERVICES

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


# Três profissionais com jornadas diferentes (weekday: 0 = segunda ... 6 = domingo):
# (nome, cor, faixas, serviços que faz por posição em SAMPLE_SERVICES, liga à conta profissional?)
DEMO_PROVIDERS = [
    (
        {"pt-BR": "Paulo Profissional", "es": "Pablo Profesional"},
        "sky",
        [(d, "09:00", "12:00") for d in range(1, 6)] + [(d, "13:00", "19:00") for d in range(1, 6)],
        [0, 1, 2, 3],  # cortes, escova e coloração
        True,
    ),
    (
        {"pt-BR": "Bianca Unhas", "es": "Bianca Uñas"},
        "rose",
        [(d, "10:00", "18:00") for d in range(2, 7)],  # quarta a domingo
        [4, 5],  # manicure e pedicure
        False,
    ),
    (
        {"pt-BR": "Diego Barbeiro", "es": "Diego Barbero"},
        "amber",
        [(0, "14:00", "20:00")] + [(d, "09:00", "13:00") for d in range(3, 6)],
        [1, 6],  # corte masculino e barba
        False,
    ),
]


def seed_demo_salon(session: Session, tenant: TenantContext) -> None:
    """Recepção, profissional e três profissionais na agenda, com jornadas diferentes."""
    password_hash = hash_password(DEMO_PASSWORD)
    users = []
    for role, local_part, name in DEMO_STAFF[tenant.locale]:
        user = User(
            name=name,
            email=f"{local_part}@{tenant.slug}.demo",
            password_hash=password_hash,
            role=role,
            must_change_password=False,
        )
        session.add(user)
        users.append(user)
    session.flush()
    professional_user = next(u for u in users if u.role == "professional")

    services = list(session.scalars(select(Offering).order_by(Offering.created_at, Offering.name)))
    by_name = {o.name: o for o in services}
    sample_names = [
        name_es if tenant.locale == "es" else name_pt for name_pt, name_es, *_ in SAMPLE_SERVICES
    ]
    for names, color, ranges, service_indexes, linked in DEMO_PROVIDERS:
        provider = Provider(
            id=uuid.uuid4(),
            name=names[tenant.locale],
            color=color,
            user_id=professional_user.id if linked else None,
            working_hours=[
                WorkingHours(weekday=day, start_time=_t(start), end_time=_t(end))
                for day, start, end in ranges
            ],
            offerings=[by_name[sample_names[i]] for i in service_indexes],
        )
        session.add(provider)
    session.flush()
    _demo_appointments(session, tenant)


DEMO_CUSTOMERS = {
    "pt-BR": [
        ("Maria Oliveira", "(11) 98111-0001"),
        ("Joana Ribeiro", "(11) 98111-0002"),
        ("Carlos Mendes", "(11) 98111-0003"),
        ("Fernanda Lima", "(11) 98111-0004"),
        ("Roberto Alves", "(11) 98111-0005"),
        ("Patrícia Gomes", "(11) 98111-0006"),
    ],
    "es": [
        ("María Benítez", "0981 110001"),
        ("Lorena Giménez", "0981 110002"),
        ("Carlos Duarte", "0981 110003"),
        ("Fernanda Ortiz", "0981 110004"),
        ("Roberto Acosta", "0981 110005"),
        ("Patricia Núñez", "0981 110006"),
    ],
}


def _demo_appointments(session: Session, tenant: TenantContext) -> None:
    """Agenda de ontem até daqui a 4 dias, com todos os status, para mostrar as cores."""
    zone = ZoneInfo(tenant.timezone)
    customers = []
    for name, phone in DEMO_CUSTOMERS[tenant.locale]:
        customer = Customer(
            id=uuid.uuid4(),
            name=name,
            search_name=normalize_text(name),
            phone_e164=normalize_phone(phone, tenant.country),
        )
        customer.consents = [
            Consent(purpose=p, policy_version="demo", source="staff")
            for p in ("service", "reminders")
        ]
        session.add(customer)
        customers.append(customer)

    today = datetime.now(zone).date()
    providers = list(session.scalars(select(Provider).order_by(Provider.name)))
    future = ["confirmed", "scheduled", "scheduled", "cancelled", "confirmed"]
    n = 0
    for offset in range(-1, 5):
        day = today + timedelta(days=offset)
        for provider in providers:
            for hours in (h for h in provider.working_hours if h.weekday == day.weekday()):
                cursor = datetime.combine(day, hours.start_time, tzinfo=zone)
                limit = datetime.combine(day, hours.end_time, tzinfo=zone)
                for _ in range(2):
                    offering = provider.offerings[n % len(provider.offerings)]
                    end = cursor + timedelta(minutes=offering.duration_min)
                    if end > limit:
                        break
                    status = (
                        ("no_show" if n % 4 == 0 else "completed") if offset < 0 else future[n % 5]
                    )
                    session.add(
                        Appointment(
                            provider_id=provider.id,
                            offering_id=offering.id,
                            customer_id=customers[n % len(customers)].id,
                            starts_at=cursor.astimezone(UTC),
                            ends_at=end.astimezone(UTC),
                            status=status,
                            source="public" if n % 3 == 0 else "staff",
                        )
                    )
                    n += 1
                    cursor = end + timedelta(minutes=30)


def _t(value: str) -> time:
    hours, minutes = map(int, value.split(":"))
    return time(hours, minutes)
