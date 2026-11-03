"""SAL-07: busca de clientes por nome ou telefone, rápida com milhares de clientes."""

import random
import time
import uuid

import pytest
from sqlalchemy import insert, text

from app.core.customers.models import Customer
from app.core.customers.search import looks_like_phone, normalize_text
from app.core.infra.db import Databases
from app.core.infra.tenancy import load_tenant, tenant_session
from app.core.tenants.provisioning import create_tenant
from app.registry import VERTICAL
from tests.test_auth import access_token, bearer

SLUG = "busca-teste"


@pytest.fixture(scope="module")
def search_tenant(db_settings, tenants):
    """Salão só destes testes, com clientes conhecidos."""
    return create_tenant(
        db_settings, slug=SLUG, name="Salão Busca", country="BR",
        owner_email="dono@busca.test", owner_name="Dono", vertical=VERTICAL,
    ).tenant  # fmt: skip


@pytest.fixture
def token(db_client, make_user, search_tenant):
    return access_token(db_client, make_user(SLUG, role="reception"))


def _add(client, token, name, phone):
    response = client.post(
        f"/t/{SLUG}/customers",
        json={"name": name, "phone": phone, "consents": ["service"]},
        headers=bearer(token),
    )
    assert response.status_code == 201, response.text
    return response.json()


def _search(client, token, q, **params):
    response = client.get(f"/t/{SLUG}/customers", params={"q": q, **params}, headers=bearer(token))
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture
def known(db_client, token):
    tag = uuid.uuid4().hex[:6]  # isola os nomes deste teste
    return {
        "joao": _add(db_client, token, f"João Conceição {tag}", "(11) 91234-0001"),
        "ana": _add(db_client, token, f"Ana Paula Silva {tag}", "(21) 99876-5432"),
        "tag": tag,
    }


# --- unidades ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "normalized"),
    [("  JOÃO   da Silva ", "joao da silva"), ("Conceição", "conceicao"), ("Ñandú", "nandu")],
)
def test_normalize_text(raw, normalized):
    assert normalize_text(raw) == normalized


@pytest.mark.parametrize(
    ("query", "is_phone"),
    [("98888-77", True), ("(11) 9888", True), ("+55 11", True), ("12", False), ("ana", False),
     ("ana 11", False)],
)  # fmt: skip
def test_phone_or_name(query, is_phone):
    assert looks_like_phone(query) is is_phone


# --- busca -------------------------------------------------------------------------------


@pytest.mark.parametrize("q", ["joao", "JOÃO", "concei", "Conceicao"])
def test_name_ignores_case_and_accents(db_client, token, known, q):
    names = [c["name"] for c in _search(db_client, token, f"{q} {known['tag']}")["items"]]

    assert names == [known["joao"]["name"]]


def test_several_words_must_all_match(db_client, token, known):
    found = _search(db_client, token, f"ana sil {known['tag']}")["items"]
    not_found = _search(db_client, token, f"ana souza {known['tag']}")["items"]

    assert [c["id"] for c in found] == [known["ana"]["id"]]
    assert not_found == []


@pytest.mark.parametrize("q", ["98765432", "9876-5432", "(21) 99876", "99876"])
def test_phone_in_any_part_and_format(db_client, token, known, q):
    ids = {c["id"] for c in _search(db_client, token, q)["items"]}

    assert known["ana"]["id"] in ids
    assert known["joao"]["id"] not in ids


def test_total_counts_the_search_results(db_client, token, known):
    page = _search(db_client, token, known["tag"], limit=1)

    assert page["total"] == 2
    assert len(page["items"]) == 1


def test_percent_and_underscore_are_literal(db_client, token, known):
    assert _search(db_client, token, "%")["items"] == []
    assert _search(db_client, token, "_")["items"] == []


def test_renamed_customer_is_found_by_the_new_name(db_client, token, known):
    db_client.patch(
        f"/t/{SLUG}/customers/{known['joao']['id']}",
        json={"name": f"Joana Ávila {known['tag']}"},
        headers=bearer(token),
    )

    assert _search(db_client, token, f"avila {known['tag']}")["total"] == 1
    assert _search(db_client, token, f"conceicao {known['tag']}")["total"] == 0


def test_search_stays_inside_the_salon(db_client, token, known, make_user):
    other = access_token(db_client, make_user("alpha", role="reception"))

    page = db_client.get(
        "/t/alpha/customers", params={"q": known["tag"]}, headers=bearer(other)
    ).json()

    assert page["total"] == 0


# --- 5 mil clientes ----------------------------------------------------------------------

FIRST = [
    "Ana",
    "Bruna",
    "Carla",
    "Débora",
    "Érica",
    "Fábio",
    "Gustavo",
    "Helena",
    "Íris",
    "João",
    "Lúcia",
    "Márcio",
    "Natália",
    "Otávio",
    "Patrícia",
    "Renata",
    "Sérgio",
    "Tânia",
]
LAST = ["Silva", "Souza", "Conceição", "Araújo", "Gonçalves", "Peña", "Benítez", "Núñez", "Lima"]


@pytest.fixture(scope="module")
def five_thousand(db_settings, search_tenant):
    rng = random.Random(7)  # noqa: S311 - dados de teste, não é segurança
    rows = []
    for i in range(5000):
        name = f"{rng.choice(FIRST)} {rng.choice(LAST)} {rng.choice(LAST)}"
        rows.append(
            {
                "id": uuid.uuid4(),
                "name": name,
                "search_name": normalize_text(name),
                "phone_e164": f"+55119{i:08d}",
            }
        )
    databases = Databases(db_settings)
    with tenant_session(databases, load_tenant(databases, SLUG)) as session:
        session.execute(insert(Customer), rows)
        session.execute(text("ANALYZE customers"))
    return rows


@pytest.mark.parametrize("q", ["gonçalves", "joao sil", "pena", "00004321", "(11) 9000"])
def test_search_with_5000_customers_takes_less_than_a_second(db_client, token, five_thousand, q):
    """Critério de aceite do SAL-07 (medido do pedido HTTP à resposta)."""
    start = time.perf_counter()
    page = _search(db_client, token, q)
    elapsed = time.perf_counter() - start

    assert page["total"] > 0
    assert elapsed < 1.0, f"busca '{q}' levou {elapsed:.3f}s"


def test_trigram_index_is_used_when_available(db_settings, five_thousand):
    databases = Databases(db_settings)
    with tenant_session(databases, load_tenant(databases, SLUG)) as session:
        has_trgm = session.execute(
            text("SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm'")
        ).first()
        if not has_trgm:
            pytest.skip("pg_trgm não existe neste Postgres (o CI tem)")
        session.execute(text("SET LOCAL enable_seqscan = off"))
        plan = "\n".join(
            session.execute(
                text("EXPLAIN SELECT id FROM customers WHERE search_name LIKE '%goncal%'")
            ).scalars()
        )
    assert "ix_customers_search_name_trgm" in plan
