"""SAL-06: profissionais com jornada semanal, folgas e serviços que realizam."""

import pytest

from app.core.infra.db import Databases
from app.core.infra.tenancy import load_tenant, tenant_session
from app.core.scheduling.models import Provider
from app.core.tenants.provisioning import seed_demo
from app.registry import VERTICAL
from tests.test_auth import access_token, bearer

MORNING_AND_AFTERNOON = [
    {"weekday": 1, "start": "09:00", "end": "12:00"},
    {"weekday": 1, "start": "13:00", "end": "19:00"},
    {"weekday": 2, "start": "09:00", "end": "18:00"},
]


@pytest.fixture
def owner_token(db_client, make_user):
    return access_token(db_client, make_user("alpha", role="owner"))


def _offering_ids(client, token, slug="alpha"):
    return {
        o["name"]: o["id"] for o in client.get(f"/t/{slug}/offerings", headers=bearer(token)).json()
    }


def _create(client, token, **overrides):
    body = {"name": "Paula Souza", **overrides}
    return client.post("/t/alpha/providers", json=body, headers=bearer(token))


def test_create_provider_with_hours_and_services(db_client, owner_token):
    offerings = _offering_ids(db_client, owner_token)

    response = _create(
        db_client,
        owner_token,
        working_hours=MORNING_AND_AFTERNOON,
        offering_ids=[offerings["Corte feminino"], offerings["Escova"]],
    )

    assert response.status_code == 201
    body = response.json()
    assert body["working_hours"] == MORNING_AND_AFTERNOON
    assert set(body["offering_ids"]) == {offerings["Corte feminino"], offerings["Escova"]}
    assert body["color"]  # escolhida automaticamente
    assert body["is_active"] is True


def test_two_providers_have_independent_schedules(db_client, owner_token):
    a = _create(db_client, owner_token, name="A", working_hours=MORNING_AND_AFTERNOON).json()
    b = _create(
        db_client,
        owner_token,
        name="B",
        working_hours=[{"weekday": 5, "start": "08:00", "end": "14:00"}],
    ).json()

    db_client.put(
        f"/t/alpha/providers/{a['id']}/working-hours",
        json={"ranges": []},
        headers=bearer(owner_token),
    )

    providers = {
        p["id"]: p for p in db_client.get("/t/alpha/providers", headers=bearer(owner_token)).json()
    }
    assert providers[a["id"]]["working_hours"] == []
    assert providers[b["id"]]["working_hours"] == [{"weekday": 5, "start": "08:00", "end": "14:00"}]


@pytest.mark.parametrize(
    ("ranges", "code"),
    [
        ([{"weekday": 1, "start": "12:00", "end": "09:00"}], "start_after_end"),
        ([{"weekday": 1, "start": "09:00", "end": "09:00"}], "start_after_end"),
        (
            [
                {"weekday": 1, "start": "09:00", "end": "13:00"},
                {"weekday": 1, "start": "12:00", "end": "18:00"},
            ],
            "overlapping_hours",
        ),
        ([{"weekday": 1, "start": "09:07", "end": "12:00"}], "invalid_time_step"),
    ],
)
def test_invalid_working_hours(db_client, owner_token, ranges, code):
    response = _create(db_client, owner_token, working_hours=ranges)

    assert response.status_code == 422
    assert response.json()["error"]["fields"][0]["code"] == code


@pytest.mark.parametrize(
    "bad_range",
    [
        {"weekday": 7, "start": "09:00", "end": "12:00"},
        {"weekday": 1, "start": "9h", "end": "12:00"},
        {"weekday": 1, "start": "24:00", "end": "12:00"},
    ],
)
def test_malformed_working_hours(db_client, owner_token, bad_range):
    assert _create(db_client, owner_token, working_hours=[bad_range]).status_code == 422


def test_back_to_back_ranges_are_fine(db_client, owner_token):
    ranges = [
        {"weekday": 3, "start": "09:00", "end": "12:00"},
        {"weekday": 3, "start": "12:00", "end": "15:00"},
    ]

    assert _create(db_client, owner_token, working_hours=ranges).status_code == 201


def test_replace_offerings_and_reject_unknown(db_client, owner_token):
    offerings = _offering_ids(db_client, owner_token)
    provider = _create(db_client, owner_token).json()
    url = f"/t/alpha/providers/{provider['id']}/offerings"

    ok = db_client.put(
        url, json={"offering_ids": [offerings["Barba"]]}, headers=bearer(owner_token)
    )
    bad = db_client.put(
        url,
        json={"offering_ids": ["00000000-0000-0000-0000-000000000000"]},
        headers=bearer(owner_token),
    )

    assert ok.json()["offering_ids"] == [offerings["Barba"]]
    assert bad.status_code == 422
    assert bad.json()["error"]["fields"][0]["code"] == "unknown_offering"


def test_link_a_user_account_once(db_client, owner_token, make_user):
    professional = make_user("alpha", role="professional")
    first = _create(db_client, owner_token, name="Com conta", user_id=str(professional.id))
    second = _create(db_client, owner_token, name="Outra", user_id=str(professional.id))

    assert first.json()["user_id"] == str(professional.id)
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "user_already_linked"


def test_owner_can_also_be_a_provider(db_client, make_user):
    owner = make_user("alpha", role="owner")
    token = access_token(db_client, owner)

    assert (
        _create(db_client, token, name="Dono que atende", user_id=str(owner.id)).status_code == 201
    )


def test_unlink_and_deactivate(db_client, owner_token, make_user):
    professional = make_user("alpha", role="professional")
    provider = _create(db_client, owner_token, user_id=str(professional.id)).json()

    response = db_client.patch(
        f"/t/alpha/providers/{provider['id']}",
        json={"user_id": None, "is_active": False},
        headers=bearer(owner_token),
    )

    assert response.json()["user_id"] is None
    active = {
        p["id"] for p in db_client.get("/t/alpha/providers", headers=bearer(owner_token)).json()
    }
    assert provider["id"] not in active


def test_time_off_uses_whole_local_days(db_client, owner_token):
    provider = _create(db_client, owner_token).json()

    response = db_client.post(
        f"/t/alpha/providers/{provider['id']}/time-off",
        json={"start_date": "2027-12-24", "end_date": "2027-12-26", "reason": "Natal"},
        headers=bearer(owner_token),
    )

    body = response.json()
    assert response.status_code == 201
    assert (body["start_date"], body["end_date"]) == ("2027-12-24", "2027-12-26")
    # meia-noite em São Paulo (UTC-3) = 03:00 UTC; termina na meia-noite do dia 27
    assert body["starts_at"].startswith("2027-12-24T03:00:00")
    assert body["ends_at"].startswith("2027-12-27T03:00:00")


def test_time_off_in_paraguay(db_client, make_user):
    token = access_token(db_client, make_user("beta", role="owner"))
    provider = db_client.post(
        "/t/beta/providers", json={"name": "Lucía"}, headers=bearer(token)
    ).json()

    body = db_client.post(
        f"/t/beta/providers/{provider['id']}/time-off",
        json={"start_date": "2027-03-01", "end_date": "2027-03-01"},
        headers=bearer(token),
    ).json()

    assert body["starts_at"].startswith("2027-03-01T03:00:00")  # Asunción, UTC-3 o ano todo
    assert body["ends_at"].startswith("2027-03-02T03:00:00")


def test_list_and_cancel_time_off(db_client, owner_token):
    provider = _create(db_client, owner_token).json()
    url = f"/t/alpha/providers/{provider['id']}/time-off"
    created = db_client.post(
        url,
        json={"start_date": "2027-01-10", "end_date": "2027-01-20"},
        headers=bearer(owner_token),
    ).json()

    listed = db_client.get(url, headers=bearer(owner_token)).json()
    deleted = db_client.delete(f"{url}/{created['id']}", headers=bearer(owner_token))
    after = db_client.get(url, headers=bearer(owner_token)).json()

    assert [t["id"] for t in listed] == [created["id"]]
    assert deleted.status_code == 204
    assert after == []


@pytest.mark.parametrize(
    ("body", "code"),
    [
        ({"start_date": "2027-01-10", "end_date": "2027-01-09"}, "end_before_start"),
        ({"start_date": "2027-01-01", "end_date": "2028-06-01"}, "too_long"),
    ],
)
def test_invalid_time_off(db_client, owner_token, body, code):
    provider = _create(db_client, owner_token).json()

    response = db_client.post(
        f"/t/alpha/providers/{provider['id']}/time-off", json=body, headers=bearer(owner_token)
    )

    assert response.json()["error"]["fields"][0]["code"] == code


def test_time_off_of_another_provider_cannot_be_cancelled_through_this_one(db_client, owner_token):
    a = _create(db_client, owner_token, name="A").json()
    b = _create(db_client, owner_token, name="B").json()
    folga = db_client.post(
        f"/t/alpha/providers/{a['id']}/time-off",
        json={"start_date": "2027-05-01", "end_date": "2027-05-01"},
        headers=bearer(owner_token),
    ).json()

    response = db_client.delete(
        f"/t/alpha/providers/{b['id']}/time-off/{folga['id']}", headers=bearer(owner_token)
    )

    assert response.status_code == 404


def test_team_sees_providers_but_only_owner_manages(db_client, make_user):
    for role in ("reception", "professional"):
        token = access_token(db_client, make_user("alpha", role=role))
        assert db_client.get("/t/alpha/providers", headers=bearer(token)).status_code == 200
        assert _create(db_client, token).status_code == 403


def test_provider_of_another_salon_is_not_found(db_client, owner_token, make_user):
    provider = _create(db_client, owner_token).json()
    beta = access_token(db_client, make_user("beta", role="owner"))

    assert (
        db_client.patch(
            f"/t/beta/providers/{provider['id']}", json={"name": "X"}, headers=bearer(beta)
        ).status_code
        == 404
    )


def test_demo_salon_has_three_providers_with_different_schedules(db_settings, tenants):
    seed_demo(db_settings, VERTICAL)  # não recria se já existir
    databases = Databases(db_settings)

    with tenant_session(databases, load_tenant(databases, "studio-bella")) as session:
        providers = session.query(Provider).order_by(Provider.name).all()
        schedules = {
            p.name: {(h.weekday, h.start_time, h.end_time) for h in p.working_hours}
            for p in providers
        }
        linked = [p.name for p in providers if p.user_id]
        offering_counts = {p.name: len(p.offerings) for p in providers}

    assert len(providers) == 3
    assert len(set(map(frozenset, schedules.values()))) == 3  # três jornadas diferentes
    assert linked == ["Paulo Profissional"]  # ligado à conta profissional da demonstração
    assert all(count > 0 for count in offering_counts.values())
