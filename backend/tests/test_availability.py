"""Horários livres (SAL-10/11) e bloqueios (SAL-10), com os casos de borda pedidos: serviço que
atravessa o almoço, virada de dia e horário de verão."""

import uuid

import pytest

from app.core.tenants.provisioning import create_tenant
from app.registry import VERTICAL
from tests.test_auth import access_token, bearer

SLUG = "livres-teste"
DST_SLUG = "livres-dst"


@pytest.fixture(scope="module")
def salons(db_settings, tenants):
    for slug in (SLUG, DST_SLUG):
        create_tenant(
            db_settings,
            slug=slug,
            name=f"Salão {slug}",
            country="BR",
            owner_email=f"dono@{slug}.test",
            owner_name="Dono",
            vertical=VERTICAL,
        )


@pytest.fixture
def owner(db_client, make_user, salons):
    return access_token(db_client, make_user(SLUG, role="owner"))


def service(client, token, minutes, slug=SLUG):
    response = client.post(
        f"/t/{slug}/services",
        json={
            "name": f"S{minutes}-{uuid.uuid4().hex[:4]}",
            "duration_min": minutes,
            "price_minor": 1000,
        },
        headers=bearer(token),
    )
    return response.json()["id"]


def provider(client, token, offering, hours, slug=SLUG, name="P"):
    return client.post(
        f"/t/{slug}/providers",
        json={
            "name": f"{name}-{uuid.uuid4().hex[:4]}",
            "offering_ids": [offering],
            "working_hours": [{"weekday": d, "start": s, "end": e} for d, s, e in hours],
        },
        headers=bearer(token),
    ).json()["id"]


def free(client, token, offering, day, slug=SLUG, provider_id=None):
    params = {"offering_id": offering, "date": day}
    if provider_id:
        params["provider_id"] = provider_id
    response = client.get(f"/t/{slug}/availability", params=params, headers=bearer(token))
    assert response.status_code == 200, response.text
    return response.json()


def times(result):
    """Início de cada horário em UTC, 'HH:MM'."""
    return [s["starts_at"][11:16] for s in result["slots"]]


def settings(client, token, slug=SLUG, **changes):
    response = client.patch(f"/t/{slug}/settings", json=changes, headers=bearer(token))
    assert response.status_code == 200, response.text


@pytest.fixture(autouse=True)
def reset_rules(db_client, owner):
    settings(db_client, owner, buffer_min=0, slot_step_min=15)
    yield


# Segunda-feira, 06/09/2027 (weekday 0). São Paulo = UTC-3: 09:00 local = 12:00 UTC.
MONDAY = "2027-09-06"
LUNCH = [(0, "09:00", "12:00"), (0, "13:00", "18:00")]


def test_free_slots_follow_the_working_hours(db_client, owner):
    s60 = service(db_client, owner, 60)
    p = provider(db_client, owner, s60, LUNCH)

    result = times(free(db_client, owner, s60, MONDAY, provider_id=p))

    assert result[0] == "12:00"  # 09:00 local
    assert "14:00" in result  # 11:00 local, termina 12:00: cabe antes do almoço
    assert "14:15" not in result  # 11:15 local atravessaria o almoço
    assert "16:00" in result  # 13:00 local
    assert result[-1] == "20:00"  # 17:00 local, termina às 18:00


def test_long_service_never_crosses_lunch(db_client, owner):
    s90 = service(db_client, owner, 90)
    p = provider(db_client, owner, s90, LUNCH)

    result = times(free(db_client, owner, s90, MONDAY, provider_id=p))

    assert "13:30" in result  # 10:30 local → 12:00
    assert "13:45" not in result  # 10:45 local → 12:15, no almoço


def test_appointment_and_minimum_interval(db_client, owner):
    s60 = service(db_client, owner, 60)
    p = provider(db_client, owner, s60, LUNCH)
    customer = db_client.post(
        f"/t/{SLUG}/customers",
        json={"name": "C", "phone": "(11) 95555-0000", "consents": ["service"]},
        headers=bearer(owner),
    ).json()["id"]
    db_client.post(
        f"/t/{SLUG}/appointments",
        json={
            "provider_id": p,
            "offering_id": s60,
            "customer_id": customer,
            "starts_at": f"{MONDAY}T13:00:00Z",
        },  # 10:00 local
        headers=bearer(owner),
    )

    without_buffer = times(free(db_client, owner, s60, MONDAY, provider_id=p))
    settings(db_client, owner, buffer_min=15)
    with_buffer = times(free(db_client, owner, s60, MONDAY, provider_id=p))

    assert "12:00" in without_buffer and "14:00" in without_buffer  # 09:00 e 11:00 encostados
    assert {"12:15", "12:30", "12:45", "13:00", "13:30"}.isdisjoint(without_buffer)
    assert "12:00" not in with_buffer and "14:00" not in with_buffer  # sem 15 min de folga
    assert "14:15" not in with_buffer  # 11:15 atravessaria o almoço de qualquer jeito


def test_buffer_also_applies_to_staff_booking_unless_squeezed(db_client, owner):
    s60 = service(db_client, owner, 60)
    p = provider(db_client, owner, s60, LUNCH)
    customer = db_client.post(
        f"/t/{SLUG}/customers",
        json={"name": "C", "phone": "(11) 95555-0001", "consents": ["service"]},
        headers=bearer(owner),
    ).json()["id"]
    body = {"provider_id": p, "offering_id": s60, "customer_id": customer}
    db_client.post(
        f"/t/{SLUG}/appointments",
        json={**body, "starts_at": f"{MONDAY}T13:00:00Z"},
        headers=bearer(owner),
    )
    settings(db_client, owner, buffer_min=15)

    close = db_client.post(
        f"/t/{SLUG}/appointments",
        json={**body, "starts_at": f"{MONDAY}T14:00:00Z"},
        headers=bearer(owner),
    )
    squeezed = db_client.post(
        f"/t/{SLUG}/appointments",
        json={**body, "starts_at": f"{MONDAY}T14:00:00Z", "allow_outside_hours": True},
        headers=bearer(owner),
    )

    assert close.json()["error"]["code"] == "too_close"
    assert squeezed.status_code == 201


def test_step_setting(db_client, owner):
    s60 = service(db_client, owner, 60)
    p = provider(db_client, owner, s60, [(0, "09:00", "11:00")])
    settings(db_client, owner, slot_step_min=30)

    assert times(free(db_client, owner, s60, MONDAY, provider_id=p)) == ["12:00", "12:30", "13:00"]


def test_no_preference_joins_everyone_who_does_the_service(db_client, owner):
    s60 = service(db_client, owner, 60)
    a = provider(db_client, owner, s60, [(0, "09:00", "10:00")], name="A")
    b = provider(db_client, owner, s60, [(0, "09:00", "10:00"), (0, "15:00", "16:00")], name="B")
    other = service(db_client, owner, 60)
    provider(db_client, owner, other, [(0, "09:00", "18:00")], name="NaoFaz")

    result = free(db_client, owner, s60, MONDAY)

    by_time = {s["starts_at"][11:16]: set(s["provider_ids"]) for s in result["slots"]}
    assert by_time == {"12:00": {a, b}, "18:00": {b}}


def test_local_day_not_utc_day(db_client, owner):
    """Horário das 22:00 em São Paulo (01:00 UTC do dia seguinte) é do dia local."""
    s60 = service(db_client, owner, 60)
    p = provider(db_client, owner, s60, [(0, "21:00", "23:00")])

    result = free(db_client, owner, s60, MONDAY, provider_id=p)

    assert [s["starts_at"] for s in result["slots"]][-1].startswith("2027-09-07T01:00:00")


# --- bloqueios ---------------------------------------------------------------------------


def block(client, token, **body):
    return client.post(f"/t/{SLUG}/blocks", json=body, headers=bearer(token))


def test_hours_block_removes_the_slots(db_client, owner):
    s60 = service(db_client, owner, 60)
    p = provider(db_client, owner, s60, LUNCH)

    created = block(
        db_client,
        owner,
        provider_id=p,
        start_date=MONDAY,
        start_time="14:00",
        end_time="16:00",
        reason="Médico",
    )
    result = times(free(db_client, owner, s60, MONDAY, provider_id=p))

    assert created.status_code == 201
    assert "16:00" in result  # 13:00 local continua
    assert {"17:00", "17:15", "18:00", "18:45"}.isdisjoint(result)  # 14:00–16:00 local bloqueado
    assert "19:00" in result  # 16:00 local volta


def test_salon_wide_holiday_removes_everyone(db_client, owner):
    s60 = service(db_client, owner, 60)
    p = provider(db_client, owner, s60, [(1, "09:00", "18:00")])

    created = block(db_client, owner, start_date="2027-09-07", reason="Feriado")

    assert created.json()["provider_id"] is None
    assert free(db_client, owner, s60, "2027-09-07", provider_id=p)["slots"] == []


def test_block_lists_appointments_already_booked(db_client, owner):
    s60 = service(db_client, owner, 60)
    p = provider(db_client, owner, s60, LUNCH)
    customer = db_client.post(
        f"/t/{SLUG}/customers",
        json={"name": "Já marcada", "phone": "(11) 95555-0002", "consents": ["service"]},
        headers=bearer(owner),
    ).json()["id"]
    db_client.post(
        f"/t/{SLUG}/appointments",
        json={
            "provider_id": p,
            "offering_id": s60,
            "customer_id": customer,
            "starts_at": "2027-09-13T13:00:00Z",
        },
        headers=bearer(owner),
    )

    created = block(db_client, owner, provider_id=p, start_date="2027-09-13", end_date="2027-09-14")

    assert [c["customer_name"] for c in created.json()["conflicts"]] == ["Já marcada"]


def test_block_refuses_booking_and_removing_it_frees_again(db_client, owner):
    s60 = service(db_client, owner, 60)
    p = provider(db_client, owner, s60, LUNCH)
    created = block(
        db_client,
        owner,
        provider_id=p,
        start_date="2027-09-20",
        start_time="09:00",
        end_time="12:00",
    ).json()
    customer = db_client.post(
        f"/t/{SLUG}/customers",
        json={"name": "C", "phone": "(11) 95555-0003", "consents": ["service"]},
        headers=bearer(owner),
    ).json()["id"]
    body = {
        "provider_id": p,
        "offering_id": s60,
        "customer_id": customer,
        "starts_at": "2027-09-20T13:00:00Z",
    }

    refused = db_client.post(f"/t/{SLUG}/appointments", json=body, headers=bearer(owner))
    db_client.delete(f"/t/{SLUG}/blocks/{created['id']}", headers=bearer(owner))
    accepted = db_client.post(f"/t/{SLUG}/appointments", json=body, headers=bearer(owner))

    assert refused.json()["error"]["code"] == "provider_time_off"
    assert accepted.status_code == 201


@pytest.mark.parametrize(
    ("body", "code"),
    [
        ({"start_time": "14:00"}, "start_and_end_required"),
        ({"start_time": "16:00", "end_time": "14:00"}, "start_after_end"),
        ({"start_time": "14:07", "end_time": "15:00"}, "invalid_time_step"),
        (
            {"start_time": "14:00", "end_time": "15:00", "end_date": "2027-09-08"},
            "hours_block_is_one_day",
        ),
        ({"end_date": "2027-09-01"}, "end_before_start"),
        ({"end_date": "2028-12-01"}, "too_long"),
        ({"provider_id": str(uuid.uuid4())}, "unknown_provider"),
    ],
)
def test_invalid_block(db_client, owner, body, code):
    response = block(db_client, owner, start_date="2027-09-06", **body)

    assert response.status_code == 422
    assert response.json()["error"]["fields"][0]["code"] == code


def test_only_the_owner_blocks(db_client, make_user, salons):
    token = access_token(db_client, make_user(SLUG, role="reception"))

    assert block(db_client, token, start_date=MONDAY).status_code == 403


# --- horário de verão --------------------------------------------------------------------


def test_daylight_saving_day_keeps_local_working_hours(db_client, make_user, salons):
    """Nova York adianta o relógio em 14/03/2027. A jornada local 09:00–12:00 continua a mesma;
    em UTC ela muda de 14:00 (EST, UTC-5) para 13:00 (EDT, UTC-4)."""
    token = access_token(db_client, make_user(DST_SLUG, role="owner"))
    settings(db_client, token, slug=DST_SLUG, timezone="America/New_York", slot_step_min=60)
    s60 = service(db_client, token, 60, slug=DST_SLUG)
    p = provider(
        db_client, token, s60, [(5, "09:00", "12:00"), (6, "09:00", "12:00")], slug=DST_SLUG
    )

    saturday = free(db_client, token, s60, "2027-03-13", slug=DST_SLUG, provider_id=p)
    sunday = free(db_client, token, s60, "2027-03-14", slug=DST_SLUG, provider_id=p)

    assert times(saturday) == ["14:00", "15:00", "16:00"]
    assert times(sunday) == ["13:00", "14:00", "15:00"]
    assert len(sunday["slots"]) == 3  # nem a mais, nem a menos
