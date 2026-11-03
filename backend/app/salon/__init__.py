"""Vertical de salões e barbearias ("Agenda Salão").

Só o que é específico de salão mora aqui: serviços com preço, página pública, dados de exemplo
e de demonstração. Agenda, clientes, login etc. vêm do core.
"""

from app.core.vertical import Vertical
from app.salon.demo import DEMO_TENANTS, seed_demo_salon
from app.salon.seed import seed_new_salon
from app.salon.services import api as services_api
from app.salon.services.public import offering_extras

VERTICAL = Vertical(
    name="salon",
    api_title="SPBella API",
    api_description=(
        "API do **SPBella** (Agenda Salão), sistema de agendamento para salões e barbearias.\n\n"
        "Guia de uso, convenções (erros, datas, valores, autenticação) e exemplos: "
        "`docs/api/README.md` no repositório."
    ),
    routers=[services_api.router],
    openapi_tags=[
        {
            "name": "Serviços",
            "description": "O que o salão oferece, com duração e preço (vertical salão).",
        },
    ],
    seed_tenant=seed_new_salon,
    demo_tenants=DEMO_TENANTS,
    seed_demo=seed_demo_salon,
    public_offering_extras=offering_extras,
)
