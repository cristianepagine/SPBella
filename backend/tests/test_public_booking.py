"""SAL-11: agendamento pela página pública, sem login."""

import uuid
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.core.tenants.provisioning import create_tenant
from app.registry import VERTICAL
from tests.test_auth import access_token, bearer
from tests.test_availability import provider, service

SLUG = "online-teste"
ALL_WEEK = [(d, "09:00", "18:00") for d in range(7)]


@pytest.fixture(scope="module")
def salon(db_settings, tenants):
    create_tenant(
        db_settings,
        slug=SLUG,
        name="Salão Online",
        country="BR",
        owner_email=f"dono@{SLUG}.test",
        owner_name="Dono",
        vertical=VERTICAL,
    )


@pytest.fixture
def owner(db_client, make_user, salon):
    token = access_token(db_client, make_user(SLUG, role="owner"))
    rules(db_client, token, min_notice_min=60, max_days_ahead=60, buffer_min=0, slot_step_min=15)
    return token


def rules(client, token, **changes):
    response = client.patch(f"/t/{SLUG}/settings", json=changes, headers=bearer(token))
    assert response.status_code == 200, response.text
    return response.json()


def local_day(days_ahead: int) -> str:
    return (
        datetime.now(ZoneInfo("America/Sao_Paulo")).date() + timedelta(days=days_ahead)
    ).isoformat()


def public_free(client, offering, day, provider_id=None):
    params = {"offering_id": offering, "date": day}
    if provider_id:
        params["provider_id"] = provider_id
    response = client.get(f"/t/{SLUG}/booking/availability", params=params)
    assert response.status_code == 200, response.text
    return response.json()["slots"]


def phone() -> str:
    return f"(11) 9{uuid.uuid4().int % 10**8:08d}"


def book(client, offering, starts_at, *, provider_id=None, **overrides):
    body = {
        "offering_id": offering,
        "provider_id": provider_id,
        "starts_at": starts_at,
        "name": "Maria Cliente",
        "phone": phone(),
        "consents": ["service", "reminders"],
        "turnstile_token": "ok",
        "locale": "pt-BR",
        **overrides,
    }
    return client.post(f"/t/{SLUG}/booking", json=body)


def test_catalog_shows_what_can_be_booked_without_personal_data(db_client, owner):
    s = service(db_client, owner, 60, slug=SLUG)
    p = provider(db_client, owner, s, ALL_WEEK, slug=SLUG, name="Paula")
    hidden = service(db_client, owner, 30, slug=SLUG)  # ninguém faz

    response = db_client.get(f"/t/{SLUG}/booking/catalog")

    assert response.status_code == 200
    body = response.json()
    offering = next(o for o in body["offerings"] if o["id"] == s)
    assert offering["extras"] == {"price_minor": 1000}
    assert hidden not in {o["id"] for o in body["offerings"]}
    professional = next(x for x in body["providers"] if x["id"] == p)
    assert set(professional) == {"id", "name", "color", "offering_ids"}
    assert body["min_notice_min"] == 60 and body["max_days_ahead"] == 60


def test_public_availability_respects_notice_and_window(db_client, owner):
    s = service(db_client, owner, 60, slug=SLUG)
    provider(db_client, owner, s, ALL_WEEK, slug=SLUG)

    assert public_free(db_client, s, local_day(5))
    assert public_free(db_client, s, local_day(61)) == []

    rules(db_client, owner, min_notice_min=7 * 24 * 60)
    assert public_free(db_client, s, local_day(5)) == []
    earliest = datetime.now(UTC) + timedelta(days=7)
    for slot in public_free(db_client, s, local_day(8)):
        assert datetime.fromisoformat(slot["starts_at"]) >= earliest


def test_booking_creates_customer_consents_and_appointment(db_client, owner):
    s = service(db_client, owner, 60, slug=SLUG)
    p = provider(db_client, owner, s, ALL_WEEK, slug=SLUG, name="Paula")
    slot = public_free(db_client, s, local_day(3), p)[0]

    response = book(db_client, s, slot["starts_at"], provider_id=p, email="Maria@Exemplo.com")

    assert response.status_code == 201, response.text
    confirmation = response.json()
    assert confirmation["provider_name"].startswith("Paula")
    assert datetime.fromisoformat(confirmation["starts_at"]) == datetime.fromisoformat(
        slot["starts_at"]
    )
    agenda = db_client.get(
        f"/t/{SLUG}/agenda", params={"start": local_day(3), "days": 1}, headers=bearer(owner)
    ).json()
    created = next(a for a in agenda["appointments"] if a["id"] == confirmation["appointment_id"])
    assert created["source"] == "public"
    customer = db_client.get(
        f"/t/{SLUG}/customers/{created['customer_id']}", headers=bearer(owner)
    ).json()
    assert customer["email"] == "maria@exemplo.com"
    assert customer["locale"] == "pt-BR"
    assert {(c["purpose"], c["source"]) for c in customer["consents"]} == {
        ("service", "public_booking"),
        ("reminders", "public_booking"),
    }
    audit = db_client.get(
        f"/t/{SLUG}/audit", params={"entity_id": customer["id"]}, headers=bearer(owner)
    ).json()
    assert {e["action"] for e in audit if e["actor_type"] == "customer"} == {
        "customer.created",
        "consent.granted",
    }


def test_same_phone_goes_to_the_existing_customer(db_client, owner):
    s = service(db_client, owner, 30, slug=SLUG)
    p = provider(db_client, owner, s, ALL_WEEK, slug=SLUG)
    number = phone()
    existing = db_client.post(
        f"/t/{SLUG}/customers",
        json={"name": "Nome Cadastrado", "phone": number, "consents": ["service"]},
        headers=bearer(owner),
    ).json()
    slot = public_free(db_client, s, local_day(4), p)[0]

    response = book(db_client, s, slot["starts_at"], provider_id=p, phone=number, name="Outro")

    assert response.status_code == 201
    agenda = db_client.get(
        f"/t/{SLUG}/agenda", params={"start": local_day(4), "days": 1}, headers=bearer(owner)
    ).json()
    created = next(
        a for a in agenda["appointments"] if a["id"] == response.json()["appointment_id"]
    )
    assert created["customer_id"] == existing["id"]
    customer = db_client.get(f"/t/{SLUG}/customers/{existing['id']}", headers=bearer(owner)).json()
    assert customer["name"] == "Nome Cadastrado"
    assert {c["purpose"] for c in customer["consents"]} == {"service", "reminders"}


def test_no_preference_goes_to_the_least_busy_professional(db_client, owner):
    s = service(db_client, owner, 60, slug=SLUG)
    a = provider(db_client, owner, s, ALL_WEEK, slug=SLUG, name="A")
    b = provider(db_client, owner, s, ALL_WEEK, slug=SLUG, name="B")
    day = local_day(6)
    first = next(x for x in public_free(db_client, s, day) if {a, b} <= set(x["provider_ids"]))
    assert book(db_client, s, first["starts_at"], provider_id=a).status_code == 201

    later = public_free(db_client, s, day)[-1]
    assert {a, b} <= set(later["provider_ids"])
    response = book(db_client, s, later["starts_at"])

    assert response.status_code == 201
    assert response.json()["provider_name"].startswith("B")


def test_taken_or_invalid_time_is_refused(db_client, owner):
    s = service(db_client, owner, 60, slug=SLUG)
    p = provider(db_client, owner, s, ALL_WEEK, slug=SLUG)
    slot = public_free(db_client, s, local_day(7), p)[0]
    assert book(db_client, s, slot["starts_at"], provider_id=p).status_code == 201

    again = book(db_client, s, slot["starts_at"], provider_id=p)
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "slot_unavailable"

    odd = datetime.fromisoformat(slot["starts_at"]) + timedelta(hours=2, minutes=5)
    assert book(db_client, s, odd.isoformat(), provider_id=p).status_code == 409
    too_soon = datetime.now(UTC).replace(second=0, microsecond=0) + timedelta(minutes=5)
    assert book(db_client, s, too_soon.isoformat(), provider_id=p).status_code == 409


@pytest.mark.parametrize(
    ("overrides", "field", "code"),
    [
        ({"consents": ["reminders"]}, "consents", "consent_required"),
        ({"phone": "123"}, "phone", "invalid_phone"),
        ({"email": "nao-e-email"}, "email", "invalid_email"),
        ({"name": "   "}, "name", "string_too_short"),
    ],
)
def test_booking_validation(db_client, owner, overrides, field, code):
    s = service(db_client, owner, 60, slug=SLUG)
    p = provider(db_client, owner, s, ALL_WEEK, slug=SLUG)
    slot = public_free(db_client, s, local_day(9), p)[0]

    response = book(db_client, s, slot["starts_at"], provider_id=p, **overrides)

    assert response.status_code == 422
    assert response.json()["error"]["fields"][0] == {"field": field, "code": code}


def test_turnstile_is_required(db_client, owner):
    s = service(db_client, owner, 60, slug=SLUG)
    p = provider(db_client, owner, s, ALL_WEEK, slug=SLUG)
    slot = public_free(db_client, s, local_day(10), p)[0]
    db_client.app.state.turnstile.result = False

    response = book(db_client, s, slot["starts_at"], provider_id=p)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "turnstile_failed"


def test_one_phone_cannot_flood_the_agenda(db_client, owner):
    s = service(db_client, owner, 15, slug=SLUG)
    p = provider(db_client, owner, s, ALL_WEEK, slug=SLUG)
    slots = public_free(db_client, s, local_day(11), p)
    number = phone()

    codes = [
        book(db_client, s, slot["starts_at"], provider_id=p, phone=number).status_code
        for slot in slots[:6]
    ]

    assert codes == [201] * 5 + [429]


def test_settings_validate_public_rules(db_client, owner):
    assert rules(db_client, owner, min_notice_min=120, max_days_ahead=30)["max_days_ahead"] == 30
    for bad in ({"min_notice_min": 7}, {"max_days_ahead": 0}, {"max_days_ahead": 400}):
        response = db_client.patch(f"/t/{SLUG}/settings", json=bad, headers=bearer(owner))
        assert response.status_code == 422
