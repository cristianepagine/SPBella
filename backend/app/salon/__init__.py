"""Vertical de salões e barbearias ("Agenda Salão").

Só o que é específico de salão mora aqui: serviços com preço, página pública, dados de exemplo
e de demonstração. Agenda, clientes, login etc. vêm do core.
"""

from app.core.vertical import Vertical
from app.salon.demo import DEMO_TENANTS, seed_demo_salon
from app.salon.seed import seed_new_salon

VERTICAL = Vertical(
    name="salon",
    api_title="SPBella API",
    api_description=(
        "API do **SPBella** (Agenda Salão), sistema de agendamento para salões e barbearias.\n\n"
        "Guia de uso, convenções (erros, datas, valores, autenticação) e exemplos: "
        "`docs/api/README.md` no repositório."
    ),
    seed_tenant=seed_new_salon,
    demo_tenants=DEMO_TENANTS,
    seed_demo=seed_demo_salon,
)
