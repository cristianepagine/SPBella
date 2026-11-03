"""SAL-09: criar, mover, cancelar e marcar falta; horário ocupado recusado, inclusive em
concorrência."""

import threading
import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from tests.conftest import FakeTurnstile
from tests.test_auth import access_token, bearer

# Segunda-feira, 06/09/2027. 10:00 em São Paulo = 13:00 UTC.
DAY = "2027-09-06"


def at(hhmm: str, day: str = DAY) -> str:
    """Hora local de São Paulo (UTC-3) → instante UTC."""
    hours, minutes = map(int, hhmm.split(":"))
    return f"{day}T{hours + 3:02d}:{minutes:02d}:00Z"


@pytest.fixture
def token(db_client, make_user):
    return access_token(db_client, make_user("alpha", role="reception"))


@pytest.fixture
def owner(db_client, make_user):
    return access_token(db_client, make_user("alpha", role="owner"))


@pytest.fixture
def ctx(db_client, owner):
    """Profissional (seg a dom, 09h–18h) que faz um serviço de 60 min; cliente com consentimento."""
    offerings = db_client.get("/t/alpha/offerings", headers=bearer(owner)).json()
    offering = next(o for o in offerings if o["duration_min"] == 60)
    other = next(o for o in offerings if o["duration_min"] == 30)
    provider = db_client.post(
        "/t/alpha/providers",
        json={
            "name": f"Prof {uuid.uuid4().hex[:4]}",
            "offering_ids": [offering["id"]],
            "working_hours": [{"weekday": d, "start": "09:00", "end": "18:00"} for d in range(7)],
        },
        headers=bearer(owner),
    ).json()
    customer = db_client.post(
        "/t/alpha/customers",
        json={"name": "Cliente Agenda", "phone": "(11) 96666-0000", "consents": ["service"]},
        headers=bearer(owner),
    ).json()
    return {
        "provider": provider["id"],
        "offering": offering["id"],
        "other_offering": other["id"],
        "customer": customer["id"],
    }


def book(client, token, ctx, starts_at, **extra):
    body = {
        "provider_id": ctx["provider"],
        "offering_id": ctx["offering"],
        "customer_id": ctx["customer"],
        "starts_at": starts_at,
        **extra,
    }
    return client.post("/t/alpha/appointments", json=body, headers=bearer(token))


def code(response):
    return response.json()["error"]["code"]


# --- criar -------------------------------------------------------------------------------


def test_book_computes_the_end_from_the_service(db_client, token, ctx):
    response = book(db_client, token, ctx, at("10:00"))

    assert response.status_code == 201
    body = response.json()
    assert body["starts_at"].startswith(f"{DAY}T13:00:00")
    assert body["ends_at"].startswith(f"{DAY}T14:00:00")
    assert (body["status"], body["source"]) == ("scheduled", "staff")


def test_taken_slot_is_refused_with_a_clear_code(db_client, token, ctx):
    book(db_client, token, ctx, at("10:00"))

    response = book(db_client, token, ctx, at("10:30"))

    assert response.status_code == 409
    assert code(response) == "slot_taken"


def test_back_to_back_is_fine(db_client, token, ctx):
    book(db_client, token, ctx, at("10:00"))

    assert book(db_client, token, ctx, at("11:00")).status_code == 201


def test_two_people_booking_the_same_slot_at_the_same_time(db_settings, token, ctx):
    """Critério de aceite: só um consegue, o outro recebe slot_taken."""
    app = create_app(db_settings)
    app.state.turnstile = FakeTurnstile()
    barrier = threading.Barrier(2)
    results: list[int] = []

    def attempt():
        with TestClient(app, raise_server_exceptions=False) as client:
            barrier.wait()  # os dois pedidos saem juntos
            response = book(client, token, ctx, at("15:00"))
            results.append(response.status_code)
            if response.status_code == 409:
                assert code(response) == "slot_taken"

    threads = [threading.Thread(target=attempt) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert sorted(results) == [201, 409]


def test_outside_working_hours_needs_explicit_squeeze(db_client, token, ctx):
    refused = book(db_client, token, ctx, at("17:30"))  # terminaria 18:30
    squeezed = book(db_client, token, ctx, at("17:30"), allow_outside_hours=True)

    assert code(refused) == "outside_working_hours"
    assert squeezed.status_code == 201


def test_squeeze_never_goes_over_another_customer(db_client, token, ctx):
    book(db_client, token, ctx, at("10:00"))

    response = book(db_client, token, ctx, at("10:00"), allow_outside_hours=True)

    assert code(response) == "slot_taken"


def test_time_off_blocks_unless_squeezed(db_client, owner, token, ctx):
    db_client.post(
        f"/t/alpha/providers/{ctx['provider']}/time-off",
        json={"start_date": "2027-09-07", "end_date": "2027-09-07"},
        headers=bearer(owner),
    )

    assert code(book(db_client, token, ctx, at("10:00", "2027-09-07"))) == "provider_time_off"


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        ("offering_id", "other_offering", "provider_cannot_do"),  # serviço que ele não faz
        ("offering_id", "missing", "unknown_offering"),
        ("customer_id", "missing", "unknown_customer"),
        ("provider_id", "missing", "unknown_provider"),
        ("starts_at", "10:07", "invalid_time_step"),
    ],
)
def test_invalid_booking(db_client, token, ctx, field, value, expected):
    resolved = {
        "other_offering": ctx["other_offering"],
        "missing": str(uuid.uuid4()),
        "10:07": at("10:07"),
    }[value]

    if field == "starts_at":
        response = book(db_client, token, ctx, resolved)
    else:
        response = book(db_client, token, ctx, at("10:00"), **{field: resolved})

    assert response.status_code == 422
    assert code(response) == expected


def test_customer_who_withdrew_consent_cannot_be_booked(db_client, token, ctx):
    db_client.post(
        f"/t/alpha/customers/{ctx['customer']}/consents",
        json={"purpose": "service", "granted": False},
        headers=bearer(token),
    )

    response = book(db_client, token, ctx, at("10:00"))

    assert code(response) == "customer_without_consent"


# --- mover -------------------------------------------------------------------------------


def test_move_to_a_free_slot(db_client, token, ctx):
    appointment = book(db_client, token, ctx, at("10:00")).json()

    moved = db_client.patch(
        f"/t/alpha/appointments/{appointment['id']}",
        json={"starts_at": at("14:00")},
        headers=bearer(token),
    )

    assert moved.status_code == 200
    assert moved.json()["starts_at"].startswith(f"{DAY}T17:00:00")
    assert book(db_client, token, ctx, at("10:00")).status_code == 201  # o antigo ficou livre


def test_move_a_little_within_its_own_time(db_client, token, ctx):
    appointment = book(db_client, token, ctx, at("10:00")).json()

    moved = db_client.patch(
        f"/t/alpha/appointments/{appointment['id']}",
        json={"starts_at": at("10:30")},
        headers=bearer(token),
    )

    assert moved.status_code == 200  # não conflita consigo mesmo


def test_move_onto_another_customer_is_refused(db_client, token, ctx):
    first = book(db_client, token, ctx, at("10:00")).json()
    book(db_client, token, ctx, at("12:00"))

    moved = db_client.patch(
        f"/t/alpha/appointments/{first['id']}",
        json={"starts_at": at("12:30")},
        headers=bearer(token),
    )

    assert code(moved) == "slot_taken"


# --- status ------------------------------------------------------------------------------


def _status(client, token, appointment_id, status, slug="alpha"):
    return client.post(
        f"/t/{slug}/appointments/{appointment_id}/status",
        json={"status": status},
        headers=bearer(token),
    )


def test_confirm_and_cancel_frees_the_slot(db_client, token, ctx):
    appointment = book(db_client, token, ctx, at("10:00")).json()

    assert _status(db_client, token, appointment["id"], "confirmed").json()["status"] == "confirmed"
    assert _status(db_client, token, appointment["id"], "cancelled").json()["status"] == "cancelled"
    assert book(db_client, token, ctx, at("10:00")).status_code == 201


def test_cancelled_cannot_be_moved(db_client, token, ctx):
    appointment = book(db_client, token, ctx, at("10:00")).json()
    _status(db_client, token, appointment["id"], "cancelled")

    moved = db_client.patch(
        f"/t/alpha/appointments/{appointment['id']}",
        json={"starts_at": at("11:00")},
        headers=bearer(token),
    )

    assert code(moved) == "not_active"


def test_reactivating_needs_the_slot_still_free(db_client, token, ctx):
    appointment = book(db_client, token, ctx, at("10:00")).json()
    _status(db_client, token, appointment["id"], "cancelled")
    book(db_client, token, ctx, at("10:00"))  # alguém pegou o horário

    assert code(_status(db_client, token, appointment["id"], "scheduled")) == "slot_taken"


def test_no_show_and_completed_only_after_the_start(db_client, token, ctx):
    future = book(db_client, token, ctx, at("10:00")).json()
    past = book(db_client, token, ctx, at("10:00", "2026-01-05"), allow_outside_hours=True).json()

    assert code(_status(db_client, token, future["id"], "no_show")) == "too_early"
    assert code(_status(db_client, token, future["id"], "completed")) == "too_early"
    assert _status(db_client, token, past["id"], "no_show").json()["status"] == "no_show"


def test_booking_shows_up_in_the_agenda(db_client, token, ctx):
    appointment = book(db_client, token, ctx, at("16:00")).json()

    agenda = db_client.get("/t/alpha/agenda", params={"start": DAY}, headers=bearer(token)).json()

    assert appointment["id"] in {a["id"] for a in agenda["appointments"]}


def test_appointment_of_another_salon_is_not_found(db_client, token, ctx, make_user):
    appointment = book(db_client, token, ctx, at("10:00")).json()
    beta = access_token(db_client, make_user("beta", role="reception"))

    assert _status(db_client, beta, appointment["id"], "cancelled", slug="beta").status_code == 404
