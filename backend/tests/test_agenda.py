"""SAL-08: agenda do dia e da semana por profissional; trava de banco contra dupla reserva."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.core.infra.db import Databases
from app.core.infra.tenancy import load_tenant, tenant_session
from app.core.scheduling.models import Appointment
from app.core.tenants.provisioning import seed_demo
from app.registry import VERTICAL
from tests.test_auth import access_token, bearer


def _utc(text_value: str) -> datetime:
    return datetime.fromisoformat(text_value).replace(tzinfo=UTC)


@pytest.fixture
def owner_token(db_client, make_user):
    return access_token(db_client, make_user("alpha", role="owner"))


@pytest.fixture
def setup(db_client, owner_token):
    """Um profissional, um serviço e um cliente no salão alpha."""
    offerings = db_client.get("/t/alpha/offerings", headers=bearer(owner_token)).json()
    offering = next(o for o in offerings if o["duration_min"] == 60)
    provider = db_client.post(
        "/t/alpha/providers",
        json={
            "name": f"Agenda {uuid.uuid4().hex[:4]}",
            "offering_ids": [offering["id"]],
            "working_hours": [{"weekday": d, "start": "09:00", "end": "18:00"} for d in range(7)],
        },
        headers=bearer(owner_token),
    ).json()
    customer = db_client.post(
        "/t/alpha/customers",
        json={"name": "Cliente Agenda", "phone": "(11) 97777-0000", "consents": ["service"]},
        headers=bearer(owner_token),
    ).json()
    return {"provider": provider, "offering": offering, "customer": customer}


def _book(db_settings, setup, starts_at: datetime, minutes=60, status="scheduled", slug="alpha"):
    databases = Databases(db_settings)
    with tenant_session(databases, load_tenant(databases, slug)) as session:
        appointment = Appointment(
            id=uuid.uuid4(),
            provider_id=setup["provider"]["id"],
            offering_id=setup["offering"]["id"],
            customer_id=setup["customer"]["id"],
            starts_at=starts_at,
            ends_at=starts_at + timedelta(minutes=minutes),
            status=status,
        )
        session.add(appointment)
    return appointment.id


def _agenda(client, token, start, **params):
    response = client.get(
        "/t/alpha/agenda", params={"start": start, **params}, headers=bearer(token)
    )
    assert response.status_code == 200, response.text
    return response.json()


def _ids(agenda):
    return {a["id"] for a in agenda["appointments"]}


# --- janelas no fuso do salão ------------------------------------------------------------


def test_day_follows_the_salon_timezone(db_client, db_settings, owner_token, setup):
    # 02:30 UTC do dia 10 = 23:30 do dia 9 em São Paulo; termina à meia-noite local
    late = _book(db_settings, setup, _utc("2027-03-10T02:30:00"), minutes=30)

    day9 = _agenda(db_client, owner_token, "2027-03-09")
    day10 = _agenda(db_client, owner_token, "2027-03-10")

    assert str(late) in _ids(day9)
    assert str(late) not in _ids(day10)
    assert day9["timezone"] == "America/Sao_Paulo"


def test_appointment_crossing_midnight_shows_on_both_days(
    db_client, db_settings, owner_token, setup
):
    late = _book(db_settings, setup, _utc("2027-03-12T02:30:00"), minutes=60)  # 23:30 → 00:30

    assert str(late) in _ids(_agenda(db_client, owner_token, "2027-03-11"))
    assert str(late) in _ids(_agenda(db_client, owner_token, "2027-03-12"))


def test_week_view_covers_seven_days(db_client, db_settings, owner_token, setup):
    monday = _book(db_settings, setup, _utc("2027-04-05T13:00:00"))
    sunday = _book(db_settings, setup, _utc("2027-04-11T13:00:00"))
    next_monday = _book(db_settings, setup, _utc("2027-04-12T13:00:00"))

    week = _agenda(db_client, owner_token, "2027-04-05", days=7)

    assert {str(monday), str(sunday)} <= _ids(week)
    assert str(next_monday) not in _ids(week)


def test_appointment_shows_service_customer_and_status(db_client, db_settings, owner_token, setup):
    booked = _book(db_settings, setup, _utc("2027-05-03T13:00:00"), status="confirmed")

    item = next(
        a
        for a in _agenda(db_client, owner_token, "2027-05-03")["appointments"]
        if a["id"] == str(booked)
    )

    assert item["offering_name"] == setup["offering"]["name"]
    assert item["customer_name"] == "Cliente Agenda"
    assert item["customer_phone_display"] == "+55 11 97777-0000"
    assert item["status"] == "confirmed"


def test_cancelled_and_no_show_still_appear(db_client, db_settings, owner_token, setup):
    cancelled = _book(db_settings, setup, _utc("2027-05-04T13:00:00"), status="cancelled")
    no_show = _book(db_settings, setup, _utc("2027-05-04T15:00:00"), status="no_show")

    statuses = {
        a["id"]: a["status"] for a in _agenda(db_client, owner_token, "2027-05-04")["appointments"]
    }

    assert statuses[str(cancelled)] == "cancelled"
    assert statuses[str(no_show)] == "no_show"


def test_filter_by_provider(db_client, db_settings, owner_token, setup):
    _book(db_settings, setup, _utc("2027-05-05T13:00:00"))

    only = _agenda(db_client, owner_token, "2027-05-05", provider_id=setup["provider"]["id"])

    assert [p["id"] for p in only["providers"]] == [setup["provider"]["id"]]
    assert {a["provider_id"] for a in only["appointments"]} == {setup["provider"]["id"]}


def test_time_off_in_the_period_is_listed(db_client, owner_token, setup):
    provider_id = setup["provider"]["id"]
    db_client.post(
        f"/t/alpha/providers/{provider_id}/time-off",
        json={"start_date": "2027-06-01", "end_date": "2027-06-02"},
        headers=bearer(owner_token),
    )

    agenda = _agenda(db_client, owner_token, "2027-06-02")

    assert any(t["provider_id"] == provider_id for t in agenda["time_off"])


@pytest.mark.parametrize("days", [0, 8])
def test_period_is_one_to_seven_days(db_client, owner_token, days):
    response = db_client.get(
        "/t/alpha/agenda", params={"start": "2027-01-01", "days": days}, headers=bearer(owner_token)
    )

    assert response.status_code == 422


# --- quem vê o quê -----------------------------------------------------------------------


def test_reception_sees_everyone(db_client, db_settings, make_user, setup):
    booked = _book(db_settings, setup, _utc("2027-07-01T13:00:00"))
    token = access_token(db_client, make_user("alpha", role="reception"))

    agenda = _agenda(db_client, token, "2027-07-01")

    assert agenda["scope"] == "all"
    assert str(booked) in _ids(agenda)


def test_professional_sees_only_own_agenda_without_phones(
    db_client, db_settings, owner_token, make_user, setup
):
    professional = make_user("alpha", role="professional")
    db_client.patch(
        f"/t/alpha/providers/{setup['provider']['id']}",
        json={"user_id": str(professional.id)},
        headers=bearer(owner_token),
    )
    mine = _book(db_settings, setup, _utc("2027-07-02T13:00:00"))
    token = access_token(db_client, professional)

    agenda = _agenda(db_client, token, "2027-07-02")

    assert agenda["scope"] == "own"
    assert [p["id"] for p in agenda["providers"]] == [setup["provider"]["id"]]
    assert str(mine) in _ids(agenda)
    assert all(a["customer_phone_display"] is None for a in agenda["appointments"])


def test_professional_cannot_peek_with_provider_filter(db_client, db_settings, make_user, setup):
    _book(db_settings, setup, _utc("2027-07-03T13:00:00"))
    token = access_token(db_client, make_user("alpha", role="professional"))  # sem ligação

    agenda = _agenda(db_client, token, "2027-07-03", provider_id=setup["provider"]["id"])

    assert agenda["own_provider_missing"] is True
    assert agenda["providers"] == []
    assert agenda["appointments"] == []


# --- trava contra dupla reserva (banco) --------------------------------------------------


def _require_gist(db_settings):
    databases = Databases(db_settings)
    with tenant_session(databases, load_tenant(databases, "alpha")) as session:
        has = session.execute(
            text("SELECT 1 FROM pg_constraint WHERE conname = 'ex_appointments_no_double_booking'")
        ).first()
    if not has:
        if not db_settings.allow_missing_pg_extensions:
            pytest.fail("a constraint contra dupla reserva deveria existir (CI/produção exigem)")
        pytest.skip("btree_gist não existe neste Postgres de teste")


def test_database_refuses_overlapping_appointments(db_settings, setup):
    _require_gist(db_settings)
    _book(db_settings, setup, _utc("2027-08-02T13:00:00"))

    with pytest.raises(IntegrityError) as exc_info:
        _book(db_settings, setup, _utc("2027-08-02T13:30:00"))

    assert exc_info.value.orig.sqlstate == "23P01"  # exclusion_violation


def test_back_to_back_is_fine_and_cancelled_frees_the_slot(db_settings, setup):
    _require_gist(db_settings)
    _book(db_settings, setup, _utc("2027-08-03T13:00:00"))
    _book(db_settings, setup, _utc("2027-08-03T14:00:00"))  # começa quando o outro termina
    _book(db_settings, setup, _utc("2027-08-03T16:00:00"), status="cancelled")

    _book(db_settings, setup, _utc("2027-08-03T16:00:00"))  # o cancelado não ocupa


def test_other_provider_at_the_same_time_is_fine(db_client, db_settings, owner_token, setup):
    _require_gist(db_settings)
    other = db_client.post(
        "/t/alpha/providers", json={"name": "Outra"}, headers=bearer(owner_token)
    ).json()
    _book(db_settings, setup, _utc("2027-08-04T13:00:00"))

    _book(db_settings, {**setup, "provider": other}, _utc("2027-08-04T13:00:00"))


# --- demonstração ------------------------------------------------------------------------


def test_demo_agenda_shows_every_status(db_client, db_settings, tenants):
    seed_demo(db_settings, VERTICAL)
    token = db_client.post(
        "/t/studio-bella/auth/login",
        json={
            "email": "recepcao@studio-bella.demo",
            "password": "demo-spbella",
            "turnstile_token": "t",
        },
    ).json()["access_token"]
    databases = Databases(db_settings)
    with tenant_session(databases, load_tenant(databases, "studio-bella")) as session:
        first = session.execute(text("SELECT min(starts_at) FROM appointments")).scalar()

    agenda = db_client.get(
        "/t/studio-bella/agenda",
        params={"start": first.astimezone(UTC).date().isoformat(), "days": 7},
        headers=bearer(token),
    ).json()

    assert len(agenda["providers"]) == 3
    assert {a["status"] for a in agenda["appointments"]} >= {"completed", "scheduled", "confirmed"}
