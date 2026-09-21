import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session, func, select

from app.core.config import settings
from app.models import Event, Ticket, TicketAvailability, User
from tests.utils.event import create_performer, create_random_event, create_venue

EVENT_TIME = "2026-10-01T20:00:00Z"


def _create_body(
    venue_id: uuid.UUID,
    performer_id: uuid.UUID,
    *,
    name: str | None = None,
    description: str = "Fighters",
    price: float = 10.0,
) -> dict:
    return {
        "name": name or "Foo",
        "description": description,
        "venue_id": str(venue_id),
        "performer_id": str(performer_id),
        "time": EVENT_TIME,
        "price": price,
    }


def test_create_event(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    venue = create_venue(db)
    performer = create_performer(db)
    data = _create_body(venue.id, performer.id, description="Fighters")
    response = client.post(
        f"{settings.API_V1_STR}/events/",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["name"] == data["name"]
    assert content["description"] == data["description"]
    assert content["venue_id"] == str(venue.id)
    assert content["performer_id"] == str(performer.id)
    assert "owner_id" in content
    assert "tickets" not in content


def test_create_event_tickets_match_seat_map(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    venue = create_venue(db, seat_map=[4, 5, 5, 7])
    performer = create_performer(db)
    response = client.post(
        f"{settings.API_V1_STR}/events/",
        headers=superuser_token_headers,
        json=_create_body(venue.id, performer.id, price=25.0),
    )
    assert response.status_code == 200
    event_id = response.json()["id"]
    detail = client.get(
        f"{settings.API_V1_STR}/events/{event_id}",
        headers=superuser_token_headers,
    )
    assert detail.status_code == 200
    tickets = detail.json()["tickets"]
    assert len(tickets) == 21
    seat = next(t for t in tickets if t["row"] == 0 and t["seat"] == 2)
    assert seat["price"] == 25.0
    assert seat["availability"] == TicketAvailability.AVAILABLE.value
    assert seat["user_id"] is None


def test_create_event_negative_price(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/events/",
        headers=superuser_token_headers,
        json=_create_body(uuid.uuid4(), uuid.uuid4(), price=-1),
    )
    assert response.status_code == 422


def test_create_event_zero_width_row(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    venue = create_venue(db, seat_map=[0])
    performer = create_performer(db)
    count_before = db.exec(select(func.count()).select_from(Event)).one()
    response = client.post(
        f"{settings.API_V1_STR}/events/",
        headers=superuser_token_headers,
        json=_create_body(venue.id, performer.id),
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid seat map"
    db.expire_all()
    count_after = db.exec(select(func.count()).select_from(Event)).one()
    assert count_after == count_before


def test_create_event_venue_not_found(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    performer = create_performer(db)
    response = client.post(
        f"{settings.API_V1_STR}/events/",
        headers=superuser_token_headers,
        json=_create_body(uuid.uuid4(), performer.id),
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Venue not found"


def test_create_event_performer_not_found(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    venue = create_venue(db)
    response = client.post(
        f"{settings.API_V1_STR}/events/",
        headers=superuser_token_headers,
        json=_create_body(venue.id, uuid.uuid4()),
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Performer not found"


def test_update_event_ignores_venue_and_price(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    event = create_random_event(db)
    other_venue = create_venue(db, seat_map=[1])
    response = client.put(
        f"{settings.API_V1_STR}/events/{event.id}",
        headers=superuser_token_headers,
        json={
            "name": "Renamed",
            "venue_id": str(other_venue.id),
            "price": 99.0,
        },
    )
    assert response.status_code == 200
    content = response.json()
    assert content["name"] == "Renamed"
    assert content["venue_id"] == str(event.venue_id)
    db.expire_all()
    tickets = db.exec(select(Ticket).where(Ticket.event_id == event.id)).all()
    assert tickets
    assert all(ticket.price == 10.0 for ticket in tickets)


def test_read_event(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    event = create_random_event(db)
    response = client.get(
        f"{settings.API_V1_STR}/events/{event.id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["name"] == event.name
    assert content["description"] == event.description
    assert content["id"] == str(event.id)
    assert content["owner_id"] == str(event.owner_id)
    tickets = content["tickets"]
    assert len(tickets) == 1
    assert tickets[0]["row"] == 0
    assert tickets[0]["seat"] == 0
    assert tickets[0]["price"] == 10.0


def test_read_event_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/events/{uuid.uuid4()}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404
    content = response.json()
    assert content["detail"] == "Event not found"


def test_read_event_other_user_ok(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    event = create_random_event(db)
    response = client.get(
        f"{settings.API_V1_STR}/events/{event.id}",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["name"] == event.name
    assert content["description"] == event.description
    assert content["id"] == str(event.id)
    assert content["owner_id"] == str(event.owner_id)


def test_read_events(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    create_random_event(db)
    create_random_event(db)
    response = client.get(
        f"{settings.API_V1_STR}/events/",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert len(content["data"]) >= 2
    for row in content["data"]:
        assert "tickets" not in row


def test_read_events_includes_other_users_event(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    event = create_random_event(db)
    response = client.get(
        f"{settings.API_V1_STR}/events/",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    ids = {row["id"] for row in content["data"]}
    assert str(event.id) in ids
    for row in content["data"]:
        assert "tickets" not in row


def test_read_event_includes_creator_name(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    event = create_random_event(db)
    owner = event.owner or db.get(User, event.owner_id)
    assert owner is not None
    response = client.get(
        f"{settings.API_V1_STR}/events/{event.id}",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 200
    assert response.json()["creator"] == owner.email


def test_read_event_marks_is_read(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    event = create_random_event(db)
    response = client.get(
        f"{settings.API_V1_STR}/events/{event.id}",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 200
    assert response.json()["is_read"] is True


def test_read_event_is_idempotent(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    event = create_random_event(db)
    url = f"{settings.API_V1_STR}/events/{event.id}"
    first = client.get(url, headers=normal_user_token_headers)
    second = client.get(url, headers=normal_user_token_headers)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["is_read"] is True
    assert second.json()["is_read"] is True


def test_read_events_is_read_false_until_opened(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    event = create_random_event(db)
    response = client.get(
        f"{settings.API_V1_STR}/events/",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 200
    row = next(r for r in response.json()["data"] if r["id"] == str(event.id))
    assert row["is_read"] is False
    assert "tickets" not in row


def test_read_events_is_read_true_after_opened(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    event = create_random_event(db)
    client.get(
        f"{settings.API_V1_STR}/events/{event.id}",
        headers=normal_user_token_headers,
    )
    response = client.get(
        f"{settings.API_V1_STR}/events/",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 200
    row = next(r for r in response.json()["data"] if r["id"] == str(event.id))
    assert row["is_read"] is True


def test_read_events_is_read_is_per_user(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    event = create_random_event(db)
    client.get(
        f"{settings.API_V1_STR}/events/{event.id}",
        headers=normal_user_token_headers,
    )
    response = client.get(
        f"{settings.API_V1_STR}/events/",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    row = next(r for r in response.json()["data"] if r["id"] == str(event.id))
    assert row["is_read"] is False


def test_set_bookmark_and_list(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    event = create_random_event(db)
    listed = client.get(
        f"{settings.API_V1_STR}/events/bookmarked",
        headers=normal_user_token_headers,
    )
    assert listed.status_code == 200
    assert str(event.id) not in {row["id"] for row in listed.json()["data"]}
    for row in listed.json()["data"]:
        assert "tickets" not in row

    set_res = client.put(
        f"{settings.API_V1_STR}/events/{event.id}/bookmark",
        headers=normal_user_token_headers,
        json={"is_bookmarked": True},
    )
    assert set_res.status_code == 200
    assert set_res.json()["is_bookmarked"] is True
    assert set_res.json()["is_read"] is False
    assert "tickets" not in set_res.json()

    listed = client.get(
        f"{settings.API_V1_STR}/events/bookmarked",
        headers=normal_user_token_headers,
    )
    row = next(r for r in listed.json()["data"] if r["id"] == str(event.id))
    assert row["is_bookmarked"] is True
    assert "tickets" not in row

    unset = client.put(
        f"{settings.API_V1_STR}/events/{event.id}/bookmark",
        headers=normal_user_token_headers,
        json={"is_bookmarked": False},
    )
    assert unset.json()["is_bookmarked"] is False
    listed = client.get(
        f"{settings.API_V1_STR}/events/bookmarked",
        headers=normal_user_token_headers,
    )
    assert str(event.id) not in {row["id"] for row in listed.json()["data"]}


def test_bookmark_is_per_user(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    event = create_random_event(db)
    client.put(
        f"{settings.API_V1_STR}/events/{event.id}/bookmark",
        headers=normal_user_token_headers,
        json={"is_bookmarked": True},
    )
    listed = client.get(
        f"{settings.API_V1_STR}/events/bookmarked",
        headers=superuser_token_headers,
    )
    assert listed.status_code == 200
    assert str(event.id) not in {row["id"] for row in listed.json()["data"]}
    for row in listed.json()["data"]:
        assert "tickets" not in row


def test_set_bookmark_not_found(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    response = client.put(
        f"{settings.API_V1_STR}/events/{uuid.uuid4()}/bookmark",
        headers=normal_user_token_headers,
        json={"is_bookmarked": True},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Event not found"


def test_bookmark_does_not_mark_read(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    event = create_random_event(db)
    client.put(
        f"{settings.API_V1_STR}/events/{event.id}/bookmark",
        headers=normal_user_token_headers,
        json={"is_bookmarked": True},
    )
    response = client.get(
        f"{settings.API_V1_STR}/events/",
        headers=normal_user_token_headers,
    )
    row = next(r for r in response.json()["data"] if r["id"] == str(event.id))
    assert row["is_bookmarked"] is True
    assert row["is_read"] is False
    assert "tickets" not in row


def test_read_does_not_bookmark(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    event = create_random_event(db)
    client.get(
        f"{settings.API_V1_STR}/events/{event.id}",
        headers=normal_user_token_headers,
    )
    response = client.get(
        f"{settings.API_V1_STR}/events/",
        headers=normal_user_token_headers,
    )
    row = next(r for r in response.json()["data"] if r["id"] == str(event.id))
    assert row["is_read"] is True
    assert row["is_bookmarked"] is False
    listed = client.get(
        f"{settings.API_V1_STR}/events/bookmarked",
        headers=normal_user_token_headers,
    )
    assert str(event.id) not in {row["id"] for row in listed.json()["data"]}


def test_update_event(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    event = create_random_event(db)
    data = {"name": "Updated name", "description": "Updated description"}
    response = client.put(
        f"{settings.API_V1_STR}/events/{event.id}",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["name"] == data["name"]
    assert content["description"] == data["description"]
    assert content["id"] == str(event.id)
    assert content["owner_id"] == str(event.owner_id)
    assert "tickets" not in content


def test_update_event_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    data = {"name": "Updated name", "description": "Updated description"}
    response = client.put(
        f"{settings.API_V1_STR}/events/{uuid.uuid4()}",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 404
    content = response.json()
    assert content["detail"] == "Event not found"


def test_update_event_not_enough_permissions(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    event = create_random_event(db)
    data = {"name": "Updated name", "description": "Updated description"}
    response = client.put(
        f"{settings.API_V1_STR}/events/{event.id}",
        headers=normal_user_token_headers,
        json=data,
    )
    assert response.status_code == 403
    content = response.json()
    assert content["detail"] == "Not enough permissions"


def test_delete_event(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    event = create_random_event(db)
    response = client.delete(
        f"{settings.API_V1_STR}/events/{event.id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["message"] == "Event deleted successfully"


def test_delete_event_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.delete(
        f"{settings.API_V1_STR}/events/{uuid.uuid4()}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404
    content = response.json()
    assert content["detail"] == "Event not found"


def test_delete_event_not_enough_permissions(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    event = create_random_event(db)
    response = client.delete(
        f"{settings.API_V1_STR}/events/{event.id}",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 403
    content = response.json()
    assert content["detail"] == "Not enough permissions"
