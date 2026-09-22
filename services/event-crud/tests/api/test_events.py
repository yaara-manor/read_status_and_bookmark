import uuid

from contracts import CALLER_HEADER, Caller, TicketAvailability
from fastapi.testclient import TestClient
from sqlmodel import Session, func, select

from app.models import Event, EventReadLink, Performer, Ticket, Venue
from tests.conftest import caller_headers
from tests.utils.event import create_performer, create_random_event, create_venue

EVENT_TIME = "2026-10-01T20:00:00Z"


def _create_body(
    venue_id: uuid.UUID,
    performer_id: uuid.UUID,
    *,
    name: str | None = None,
    description: str = "Fighters",
    price: float = 10.0,
) -> dict[str, object]:
    return {
        "name": name or "Foo",
        "description": description,
        "venue_id": str(venue_id),
        "performer_id": str(performer_id),
        "time": EVENT_TIME,
        "price": price,
    }


def _read_link_count(db: Session, user_id: uuid.UUID, event_id: uuid.UUID) -> int:
    db.expire_all()
    return db.exec(
        select(func.count())
        .select_from(EventReadLink)
        .where(EventReadLink.user_id == user_id, EventReadLink.event_id == event_id)
    ).one()


def test_invalid_caller_is_401(client: TestClient) -> None:
    response = client.get("/events", headers={CALLER_HEADER: "%%%"})
    assert response.status_code == 401
    assert response.json()["detail"] == "missing caller"


def test_missing_caller(client: TestClient) -> None:
    response = client.get("/events")
    assert response.status_code == 401
    assert response.json()["detail"] == "missing caller"


def test_invalid_internal_key(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    response = client.get(
        "/events",
        headers={**superuser_headers, "X-Internal-Key": "wrong-key"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "invalid internal key"


def test_inactive_caller(client: TestClient) -> None:
    caller = Caller(
        id=uuid.uuid4(),
        is_active=False,
        is_superuser=False,
        display_name="Inactive",
    )
    response = client.get("/events", headers=caller_headers(caller))
    assert response.status_code == 400
    assert response.json()["detail"] == "Inactive user"


def test_create_event(
    client: TestClient,
    superuser: Caller,
    superuser_headers: dict[str, str],
    db: Session,
) -> None:
    venue = create_venue(db)
    performer = create_performer(db)
    data = _create_body(venue.id, performer.id, description="Fighters")
    response = client.post("/events", headers=superuser_headers, json=data)
    assert response.status_code == 200
    content = response.json()
    assert content["name"] == data["name"]
    assert content["description"] == data["description"]
    assert content["venue_id"] == str(venue.id)
    assert content["performer_id"] == str(performer.id)
    assert content["owner_id"] == str(superuser.id)
    assert content["creator"] == superuser.display_name
    assert "tickets" not in content


def test_create_event_tickets_match_seat_map(
    client: TestClient, superuser_headers: dict[str, str], db: Session
) -> None:
    venue = create_venue(db, seat_map=[4, 5, 5, 7])
    performer = create_performer(db)
    response = client.post(
        "/events",
        headers=superuser_headers,
        json=_create_body(venue.id, performer.id, price=25.0),
    )
    assert response.status_code == 200
    event_id = response.json()["id"]
    detail = client.get(f"/events/{event_id}", headers=superuser_headers)
    assert detail.status_code == 200
    tickets = detail.json()["tickets"]
    assert len(tickets) == 21
    seat = next(t for t in tickets if t["row"] == 0 and t["seat"] == 2)
    assert seat["price"] == 25.0
    assert seat["availability"] == TicketAvailability.AVAILABLE.value
    assert seat["user_id"] is None


def test_create_event_negative_price(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    response = client.post(
        "/events",
        headers=superuser_headers,
        json=_create_body(uuid.uuid4(), uuid.uuid4(), price=-1),
    )
    assert response.status_code == 422


def test_create_event_zero_width_row(
    client: TestClient, superuser_headers: dict[str, str], db: Session
) -> None:
    venue = create_venue(db, seat_map=[0])
    performer = create_performer(db)
    count_before = db.exec(select(func.count()).select_from(Event)).one()
    response = client.post(
        "/events",
        headers=superuser_headers,
        json=_create_body(venue.id, performer.id),
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid seat map"
    db.expire_all()
    count_after = db.exec(select(func.count()).select_from(Event)).one()
    assert count_after == count_before


def test_create_event_venue_not_found(
    client: TestClient, superuser_headers: dict[str, str], db: Session
) -> None:
    performer = create_performer(db)
    response = client.post(
        "/events",
        headers=superuser_headers,
        json=_create_body(uuid.uuid4(), performer.id),
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Venue not found"


def test_create_event_performer_not_found(
    client: TestClient, superuser_headers: dict[str, str], db: Session
) -> None:
    venue = create_venue(db)
    response = client.post(
        "/events",
        headers=superuser_headers,
        json=_create_body(venue.id, uuid.uuid4()),
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Performer not found"


def test_update_event_ignores_venue_and_price(
    client: TestClient,
    superuser_headers: dict[str, str],
    db: Session,
    superuser: Caller,
) -> None:
    event = create_random_event(db, creator="Owner", owner_id=uuid.uuid4())
    assert event.owner_id != superuser.id
    other_venue = create_venue(db, seat_map=[1])
    response = client.put(
        f"/events/{event.id}",
        headers=superuser_headers,
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
    client: TestClient,
    superuser_headers: dict[str, str],
    db: Session,
    superuser: Caller,
) -> None:
    event = create_random_event(
        db, creator=superuser.display_name, owner_id=superuser.id
    )
    response = client.get(f"/events/{event.id}", headers=superuser_headers)
    assert response.status_code == 200
    content = response.json()
    assert content["name"] == event.name
    assert content["description"] == event.description
    assert content["id"] == str(event.id)
    assert content["owner_id"] == str(event.owner_id)
    assert content["is_read"] is True
    tickets = content["tickets"]
    assert len(tickets) == 1
    assert tickets[0]["row"] == 0
    assert tickets[0]["seat"] == 0
    assert tickets[0]["price"] == 10.0


def test_read_event_not_found(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    response = client.get(f"/events/{uuid.uuid4()}", headers=superuser_headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "Event not found"


def test_read_event_other_user_ok(
    client: TestClient,
    normal_user_headers: dict[str, str],
    db: Session,
    superuser: Caller,
) -> None:
    event = create_random_event(
        db, creator=superuser.display_name, owner_id=superuser.id
    )
    response = client.get(f"/events/{event.id}", headers=normal_user_headers)
    assert response.status_code == 200
    content = response.json()
    assert content["name"] == event.name
    assert content["description"] == event.description
    assert content["id"] == str(event.id)
    assert content["owner_id"] == str(event.owner_id)


def test_read_events(
    client: TestClient,
    superuser_headers: dict[str, str],
    db: Session,
    superuser: Caller,
) -> None:
    create_random_event(db, creator=superuser.display_name, owner_id=superuser.id)
    create_random_event(db, creator=superuser.display_name, owner_id=superuser.id)
    response = client.get("/events", headers=superuser_headers)
    assert response.status_code == 200
    content = response.json()
    assert len(content["data"]) >= 2
    for row in content["data"]:
        assert "tickets" not in row


def test_read_events_newest_first(
    client: TestClient,
    superuser_headers: dict[str, str],
    db: Session,
    superuser: Caller,
) -> None:
    older = create_random_event(
        db, creator=superuser.display_name, owner_id=superuser.id
    )
    newer = create_random_event(
        db, creator=superuser.display_name, owner_id=superuser.id
    )
    response = client.get("/events", headers=superuser_headers)
    assert response.status_code == 200
    ids = [row["id"] for row in response.json()["data"]]
    assert ids.index(str(newer.id)) < ids.index(str(older.id))


def test_read_events_includes_other_users_event(
    client: TestClient,
    normal_user_headers: dict[str, str],
    db: Session,
    superuser: Caller,
) -> None:
    event = create_random_event(
        db, creator=superuser.display_name, owner_id=superuser.id
    )
    response = client.get("/events", headers=normal_user_headers)
    assert response.status_code == 200
    content = response.json()
    ids = {row["id"] for row in content["data"]}
    assert str(event.id) in ids
    for row in content["data"]:
        assert "tickets" not in row


def test_read_event_includes_creator_name(
    client: TestClient, normal_user_headers: dict[str, str], db: Session
) -> None:
    event = create_random_event(db, creator="Ada Lovelace", owner_id=uuid.uuid4())
    response = client.get(f"/events/{event.id}", headers=normal_user_headers)
    assert response.status_code == 200
    assert response.json()["creator"] == "Ada Lovelace"


def test_read_event_marks_is_read(
    client: TestClient,
    normal_user_headers: dict[str, str],
    db: Session,
    normal_user: Caller,
) -> None:
    event = create_random_event(db, creator="Ada Lovelace", owner_id=uuid.uuid4())
    response = client.get(f"/events/{event.id}", headers=normal_user_headers)
    assert response.status_code == 200
    assert response.json()["is_read"] is True
    assert len(response.json()["tickets"]) == 1
    assert _read_link_count(db, normal_user.id, event.id) == 1


def test_read_event_is_idempotent(
    client: TestClient,
    normal_user_headers: dict[str, str],
    db: Session,
    normal_user: Caller,
) -> None:
    event = create_random_event(db, creator="Ada Lovelace", owner_id=uuid.uuid4())
    url = f"/events/{event.id}"
    first = client.get(url, headers=normal_user_headers)
    second = client.get(url, headers=normal_user_headers)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["is_read"] is True
    assert second.json()["is_read"] is True
    assert _read_link_count(db, normal_user.id, event.id) == 1


def test_read_events_is_read_false_until_opened(
    client: TestClient, normal_user_headers: dict[str, str], db: Session
) -> None:
    event = create_random_event(db, creator="Ada Lovelace", owner_id=uuid.uuid4())
    response = client.get("/events", headers=normal_user_headers)
    assert response.status_code == 200
    row = next(r for r in response.json()["data"] if r["id"] == str(event.id))
    assert row["is_read"] is False
    assert row["is_bookmarked"] is False
    assert "tickets" not in row


def test_read_events_is_read_true_after_opened(
    client: TestClient, normal_user_headers: dict[str, str], db: Session
) -> None:
    event = create_random_event(db, creator="Ada Lovelace", owner_id=uuid.uuid4())
    client.get(f"/events/{event.id}", headers=normal_user_headers)
    response = client.get("/events", headers=normal_user_headers)
    assert response.status_code == 200
    row = next(r for r in response.json()["data"] if r["id"] == str(event.id))
    assert row["is_read"] is True


def test_read_events_is_read_is_per_user(
    client: TestClient,
    normal_user_headers: dict[str, str],
    superuser_headers: dict[str, str],
    db: Session,
) -> None:
    event = create_random_event(db, creator="Ada Lovelace", owner_id=uuid.uuid4())
    client.get(f"/events/{event.id}", headers=normal_user_headers)
    response = client.get("/events", headers=superuser_headers)
    assert response.status_code == 200
    row = next(r for r in response.json()["data"] if r["id"] == str(event.id))
    assert row["is_read"] is False


def test_set_bookmark_and_list(
    client: TestClient, normal_user_headers: dict[str, str], db: Session
) -> None:
    event = create_random_event(db, creator="Ada Lovelace", owner_id=uuid.uuid4())
    listed = client.get("/events/bookmarked", headers=normal_user_headers)
    assert listed.status_code == 200
    assert str(event.id) not in {row["id"] for row in listed.json()["data"]}
    for row in listed.json()["data"]:
        assert "tickets" not in row

    set_res = client.put(
        f"/events/{event.id}/bookmark",
        headers=normal_user_headers,
        json={"is_bookmarked": True},
    )
    assert set_res.status_code == 200
    assert set_res.json()["is_bookmarked"] is True
    assert set_res.json()["is_read"] is False
    assert "tickets" not in set_res.json()

    listed = client.get("/events/bookmarked", headers=normal_user_headers)
    row = next(r for r in listed.json()["data"] if r["id"] == str(event.id))
    assert row["is_bookmarked"] is True
    assert "tickets" not in row

    unset = client.put(
        f"/events/{event.id}/bookmark",
        headers=normal_user_headers,
        json={"is_bookmarked": False},
    )
    assert unset.json()["is_bookmarked"] is False
    listed = client.get("/events/bookmarked", headers=normal_user_headers)
    assert str(event.id) not in {row["id"] for row in listed.json()["data"]}


def test_bookmark_is_per_user(
    client: TestClient,
    normal_user_headers: dict[str, str],
    superuser_headers: dict[str, str],
    db: Session,
) -> None:
    event = create_random_event(db, creator="Ada Lovelace", owner_id=uuid.uuid4())
    client.put(
        f"/events/{event.id}/bookmark",
        headers=normal_user_headers,
        json={"is_bookmarked": True},
    )
    listed = client.get("/events/bookmarked", headers=superuser_headers)
    assert listed.status_code == 200
    assert str(event.id) not in {row["id"] for row in listed.json()["data"]}
    for row in listed.json()["data"]:
        assert "tickets" not in row


def test_set_bookmark_not_found(
    client: TestClient, normal_user_headers: dict[str, str]
) -> None:
    response = client.put(
        f"/events/{uuid.uuid4()}/bookmark",
        headers=normal_user_headers,
        json={"is_bookmarked": True},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Event not found"


def test_bookmark_does_not_mark_read(
    client: TestClient, normal_user_headers: dict[str, str], db: Session
) -> None:
    event = create_random_event(db, creator="Ada Lovelace", owner_id=uuid.uuid4())
    client.put(
        f"/events/{event.id}/bookmark",
        headers=normal_user_headers,
        json={"is_bookmarked": True},
    )
    response = client.get("/events", headers=normal_user_headers)
    row = next(r for r in response.json()["data"] if r["id"] == str(event.id))
    assert row["is_bookmarked"] is True
    assert row["is_read"] is False
    assert "tickets" not in row


def test_read_does_not_bookmark(
    client: TestClient, normal_user_headers: dict[str, str], db: Session
) -> None:
    event = create_random_event(db, creator="Ada Lovelace", owner_id=uuid.uuid4())
    client.get(f"/events/{event.id}", headers=normal_user_headers)
    response = client.get("/events", headers=normal_user_headers)
    row = next(r for r in response.json()["data"] if r["id"] == str(event.id))
    assert row["is_read"] is True
    assert row["is_bookmarked"] is False
    listed = client.get("/events/bookmarked", headers=normal_user_headers)
    assert str(event.id) not in {row["id"] for row in listed.json()["data"]}


def test_update_event(
    client: TestClient,
    superuser_headers: dict[str, str],
    db: Session,
    superuser: Caller,
) -> None:
    event = create_random_event(db, creator="Owner", owner_id=uuid.uuid4())
    assert event.owner_id != superuser.id
    data = {"name": "Updated name", "description": "Updated description"}
    response = client.put(
        f"/events/{event.id}",
        headers=superuser_headers,
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
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    data = {"name": "Updated name", "description": "Updated description"}
    response = client.put(
        f"/events/{uuid.uuid4()}",
        headers=superuser_headers,
        json=data,
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Event not found"


def test_owner_can_update_and_delete(
    client: TestClient,
    normal_user: Caller,
    normal_user_headers: dict[str, str],
    db: Session,
) -> None:
    event = create_random_event(
        db, creator=normal_user.display_name, owner_id=normal_user.id
    )
    updated = client.put(
        f"/events/{event.id}",
        headers=normal_user_headers,
        json={"name": "Mine"},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Mine"
    deleted = client.delete(f"/events/{event.id}", headers=normal_user_headers)
    assert deleted.status_code == 200
    assert deleted.json()["message"] == "Event deleted successfully"


def test_update_event_not_enough_permissions(
    client: TestClient,
    normal_user_headers: dict[str, str],
    db: Session,
    normal_user: Caller,
) -> None:
    event = create_random_event(db, creator="Owner", owner_id=uuid.uuid4())
    assert event.owner_id != normal_user.id
    data = {"name": "Updated name", "description": "Updated description"}
    response = client.put(
        f"/events/{event.id}",
        headers=normal_user_headers,
        json=data,
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Not enough permissions"


def test_delete_event(
    client: TestClient,
    superuser_headers: dict[str, str],
    db: Session,
    superuser: Caller,
) -> None:
    event = create_random_event(db, creator="Owner", owner_id=uuid.uuid4())
    assert event.owner_id != superuser.id
    response = client.delete(f"/events/{event.id}", headers=superuser_headers)
    assert response.status_code == 200
    assert response.json()["message"] == "Event deleted successfully"


def test_delete_event_not_found(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    response = client.delete(f"/events/{uuid.uuid4()}", headers=superuser_headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "Event not found"


def _venue(db: Session, name: str) -> Venue:
    venue = Venue(name=name, city="Tel Aviv", country="Israel", seat_map=[1])
    db.add(venue)
    db.commit()
    db.refresh(venue)
    return venue


def _performer(db: Session, name: str, genre: str = "MUSIC") -> Performer:
    performer = Performer(name=name, genre=genre, description=None)
    db.add(performer)
    db.commit()
    db.refresh(performer)
    return performer


def test_suggest_venues_prefix(
    client: TestClient, superuser_headers: dict[str, str], db: Session
) -> None:
    hall = _venue(db, "Main Hall Annex")
    other = _venue(db, "Drama House")
    response = client.get("/venues", headers=superuser_headers, params={"q": "Ma"})
    assert response.status_code == 200
    data = response.json()["data"]
    ids = {row["id"] for row in data}
    assert str(hall.id) in ids
    assert str(other.id) not in ids
    assert all(row["name"].lower().startswith("ma") for row in data)


def test_suggest_venues_case_insensitive(
    client: TestClient, superuser_headers: dict[str, str], db: Session
) -> None:
    hall = _venue(db, "Main Hall Case")
    response = client.get("/venues", headers=superuser_headers, params={"q": "ma"})
    assert response.status_code == 200
    ids = {row["id"] for row in response.json()["data"]}
    assert str(hall.id) in ids


def test_suggest_performers_prefix(
    client: TestClient, superuser_headers: dict[str, str], db: Session
) -> None:
    band = _performer(db, "The Bandstand")
    other = _performer(db, "Someone Else", genre="SPORT")
    response = client.get("/performers", headers=superuser_headers, params={"q": "The"})
    assert response.status_code == 200
    data = response.json()["data"]
    match = next(row for row in data if row["id"] == str(band.id))
    assert match["name"] == "The Bandstand"
    assert match["genre"] == "MUSIC"
    assert str(other.id) not in {row["id"] for row in data}


def test_suggest_empty_query(
    client: TestClient, superuser_headers: dict[str, str], db: Session
) -> None:
    _venue(db, "Empty Query Hall")
    for query in ("", "   "):
        response = client.get("/venues", headers=superuser_headers, params={"q": query})
        assert response.status_code == 200
        assert response.json()["data"] == []


def test_suggest_limit_capped(
    client: TestClient, superuser_headers: dict[str, str], db: Session
) -> None:
    for index in range(12):
        _venue(db, f"Cap{index:02d} Hall")
    response = client.get(
        "/venues", headers=superuser_headers, params={"q": "Cap", "limit": 1000}
    )
    assert response.status_code == 200
    assert len(response.json()["data"]) == 10


def test_suggest_percent_is_literal(
    client: TestClient, superuser_headers: dict[str, str], db: Session
) -> None:
    literal = _venue(db, "%Only Hall")
    plain = _venue(db, "Plain Hall")
    response = client.get("/venues", headers=superuser_headers, params={"q": "%"})
    assert response.status_code == 200
    ids = {row["id"] for row in response.json()["data"]}
    assert ids == {str(literal.id)}
    assert str(plain.id) not in ids


def test_delete_event_not_enough_permissions(
    client: TestClient,
    normal_user_headers: dict[str, str],
    db: Session,
    normal_user: Caller,
) -> None:
    event = create_random_event(db, creator="Owner", owner_id=uuid.uuid4())
    assert event.owner_id != normal_user.id
    response = client.delete(f"/events/{event.id}", headers=normal_user_headers)
    assert response.status_code == 403
    assert response.json()["detail"] == "Not enough permissions"
