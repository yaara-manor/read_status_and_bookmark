> **Superseded.** The monolith is gone. Public routes live in the contracts catalog. User writes live in `services/user-crud`. Event writes live in `services/event-crud`. Do not follow the steps below.

# Event Schema Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace items with events, venues, performers, and tickets, and serve them from `/events` using the existing seen and bookmark behavior.

**Architecture:** `item` is dropped and recreated as `event` in one Alembic revision. `crud.create_event` is the only writer of an event and its tickets (one transaction), and both `POST /events/` and `init_db` call it. List responses use `EventPublic` (no tickets). `GET /events/{id}` uses `EventDetail`, which adds the ticket list. `Item` and `/items` are deleted in the same change, not aliased.

**Tech Stack:** FastAPI, SQLModel, Alembic, Postgres arrays and enums, pytest against the existing `app_test` database.

**Spec:** `docs/superpowers/specs/2026-09-21-event-schema-design.md`

## Global Constraints

- `user` is unchanged. Primary keys stay UUIDs. Strings are max 255.
- Event keeps `owner_id` (creator) and `created_at`. Owner or superuser may update and delete. Deleting a user deletes the events they own.
- Seen and bookmark stay many-to-many. Opening an event marks it seen. Bookmark body is `{ "is_bookmarked": bool }`.
- Create writes one `AVAILABLE` ticket per seat. `user_id` is null. Price on every ticket is the request price. Coordinates are 0-based: on `[4, 5, 5, 7]`, the 3rd seat in the 1st row is `(0, 2)` (21 tickets).
- `venue_id` and `price` are not on the update schema.
- Existing item rows are discarded.
- Routes are only the old item routes, renamed to `/events`. No venue, performer, or ticket routes.
- Do not edit the frontend client, pages, or Playwright tests.
- New migration `down_revision` is `2fbe5976c82a`. Do not edit `backend/app/alembic/versions/2fbe5976c82a_add_item_bookmark_link.py`.
- Error strings: `Event not found`, `Venue not found`, `Performer not found`, `Invalid seat map`, `Not enough permissions`, `Event deleted successfully`.
- Negative price is 422. Empty seat map or a width below 1 is 400 and creates no event.
- Seed, only when no venue is named `Main Hall`: venue `Main Hall` / `Tel Aviv` / `Israel` / `[4, 5, 5, 7]`; performer `The Band` / `MUSIC` / `Live music`; event `Opening Night` / `First show of the season` / `2026-10-01T20:00:00Z` / price `25.0`, owned by the first superuser.
- Deleting a buyer sets `ticket.user_id` to null and leaves `availability` as stored.
- Deleting a venue or performer is blocked while an event points at it (`ondelete="RESTRICT"`).
- No service class, repository, seat object, ticket-builder module, or custom exception type. `LookupError` and `ValueError` are enough. Models stay in `backend/app/models.py`. Ticket generation stays inside `crud.create_event`.
- `EventPublic` has no `tickets` field. `EventDetail` subclasses it and adds `tickets`. Do not push `models.py` or the route module over 1000 lines. Delete `Item`, `items.py`, `tests/utils/item.py`, and `test_items.py`. No re-export aliases.
- `git add` only the files named in that task. The worktree has unrelated frontend edits.
- Postgres enum type names are `performer_genre` and `ticket_availability`. The model uses those names and does not create a second type.

## File structure

- Modify `backend/app/models.py` — delete every `Item*` model. Add `Venue`, `Performer`, `PerformerGenre`, `Event`, `Ticket`, `TicketAvailability`, `EventReadLink`, and `EventBookmarkLink`. `User` relationships become `events`, `read_events`, `bookmarked_events`.
- Create `backend/app/alembic/versions/b7c4e2a91d08_replace_item_with_event.py` — drop item tables, create the new ones. Downgrade recreates empty `item`, `itemreadlink`, and `itembookmarklink`.
- Modify `backend/app/crud.py` — delete `create_item`. Add `create_event`.
- Create `backend/app/api/routes/events.py` — the `/events` router. Delete `backend/app/api/routes/items.py`.
- Modify `backend/app/api/main.py` — include `events.router` instead of `items.router`.
- Modify `backend/app/api/routes/users.py` — delete owned `Event` rows instead of `Item` rows.
- Modify `backend/app/core/db.py` — seed venue, performer, and event (Task 2).
- Modify `backend/tests/conftest.py` — cleanup deletes events, then venues, performers, and users.
- Create `backend/tests/utils/event.py`. Delete `backend/tests/utils/item.py`.
- Create `backend/tests/test_create_event.py` and `backend/tests/api/routes/test_events.py`. Delete `backend/tests/api/routes/test_items.py`.
- Modify `backend/tests/api/routes/test_users.py` — user delete removes owned events; deleting a buyer clears `ticket.user_id`.

Link classes sit above `User` because `link_model` is evaluated immediately. `User` may reference `Event` before that class exists, same as today's `Item` reference.

---

### Task 1: Replace items with events

**Files:**
- Create: `backend/tests/test_create_event.py`
- Create: `backend/tests/api/routes/test_events.py`
- Create: `backend/tests/utils/event.py`
- Create: `backend/app/api/routes/events.py`
- Create: `backend/app/alembic/versions/b7c4e2a91d08_replace_item_with_event.py`
- Modify: `backend/app/models.py`
- Modify: `backend/app/crud.py`
- Modify: `backend/app/api/main.py`
- Modify: `backend/app/api/routes/users.py`
- Modify: `backend/tests/conftest.py`
- Modify: `backend/tests/api/routes/test_users.py`
- Delete: `backend/app/api/routes/items.py`
- Delete: `backend/tests/utils/item.py`
- Delete: `backend/tests/api/routes/test_items.py`
- Test: `backend/tests/test_create_event.py`, `backend/tests/api/routes/test_events.py`, `backend/tests/api/routes/test_users.py`

**Interfaces:**

- `crud.create_event(session, event_in: EventCreate, owner_id) -> Event` — loads venue and performer, rejects a missing row or a bad seat map before insert, writes one `AVAILABLE` ticket per seat at `event_in.price`, commits once.
- `EventCreate` fields: `name`, `description | None`, `venue_id`, `performer_id`, `time`, `price` (`>= 0`). `EventUpdate` fields: optional `name`, `description`, `time`, `performer_id`.
- `EventPublic.from_event(event, *, is_read=False, is_bookmarked=False) -> EventPublic` — copies the event and sets `creator` from the owner's full name, or email when the name is empty.
- `EventDetail(EventPublic)` adds `tickets: list[TicketPublic]`. `TicketPublic` fields: `id`, `row`, `seat`, `price`, `availability`, `user_id | None`.
- `create_random_event(db) -> Event` — one seat (`[1]`), price `10.0`, random owner, venue, and performer.
- Raises `LookupError("Venue")` or `LookupError("Performer")` when that row is missing. Raises `ValueError("Invalid seat map")` when `seat_map` is empty or any width is `< 1`.

**Tables:** `venue` (`city`, `country`, `name`, `seat_map` integer array). `performer` (`name`, `genre`, optional `description`). `event` (`name`, optional `description`, timezone-aware `time`, `venue_id` RESTRICT, `performer_id` RESTRICT, `owner_id` CASCADE, `created_at`). `ticket` (`event_id` CASCADE, nullable `user_id` SET NULL, `row`, `seat`, `price >= 0`, `availability`; unique `(event_id, row, seat)`; `row >= 0` and `seat >= 0`). `eventreadlink` and `eventbookmarklink` composite PK `(user_id, event_id)`, both FKs CASCADE. Upgrade deletes item rows and links, then drops `itembookmarklink`, `itemreadlink`, and `item`.

- [ ] **Step 1: Write the failing tests**

`tests/test_create_event.py`

- `test_create_event_writes_one_ticket_per_seat` — seat map `[4, 5, 5, 7]` and price `25.0` yields 21 tickets; `(0, 2)` is `25.0`, `AVAILABLE`, `user_id` null.
- `test_create_event_rejects_zero_width_row` — seat map `[0]` raises `ValueError` matching `Invalid seat map` and the event count stays the same.

`tests/api/routes/test_events.py` — move the current item tests onto `/events` and `name` (not `title`). Detail strings become `Event not found` and `Event deleted successfully`. List and bookmark payloads have no `tickets` key. `GET /events/{id}` for a random event returns one ticket at `(0, 0)` priced `10.0`.

Additional cases:

- `test_create_event` — post against a one-seat venue returns `name`, `description`, `venue_id`, `performer_id`, `owner_id`, and no `tickets`.
- `test_create_event_tickets_match_seat_map` — post price `25.0` on `[4, 5, 5, 7]`; the following GET returns 21 tickets, including `(0, 2)` at `25.0`, `AVAILABLE`, `user_id` null.
- `test_create_event_negative_price` — price `-1` returns 422. Body validation runs before a venue lookup, so the ids can be random.
- `test_create_event_zero_width_row` — a stored seat map `[0]` returns 400 `Invalid seat map` and the event count stays the same.
- `test_create_event_venue_not_found` — unknown `venue_id` returns 404 `Venue not found`.
- `test_create_event_performer_not_found` — unknown `performer_id` returns 404 `Performer not found`.
- `test_update_event_ignores_venue_and_price` — a body that also sends another `venue_id` and `price` renames the event and leaves `venue_id` and ticket price unchanged.

`tests/api/routes/test_users.py`

- `test_delete_user_deletes_owned_events` — deleting the owner returns 200, and the event and its tickets are gone.
- `test_delete_buyer_clears_ticket_user_id` — a ticket marked `BOOKED` for another user keeps the event and `BOOKED`, and `user_id` becomes null after that user is deleted.

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && uv run pytest tests/test_create_event.py::test_create_event_writes_one_ticket_per_seat -v`

Expected: FAIL with `ImportError` (`EventCreate` or `crud.create_event` missing).

- [ ] **Step 3: Implement models, migration, crud, and routes**

Replace `Item*` models and `create_item`. Point `api/main.py` at `events.router`. In `users.py`, delete `Event` rows for that `owner_id` before deleting the user. Session cleanup deletes `Event`, then `Venue`, then `Performer`, then `User`.

Route handlers, same permission and seen/bookmark behavior as the item routes:

- `read_events(session, current_user, skip=0, limit=100) -> EventsPublic` — newest `created_at` first, with this user's seen and bookmark flags, no tickets.
- `read_bookmarked_events(session, current_user, skip=0, limit=100) -> EventsPublic` — that user's bookmarks, `is_bookmarked` true, no tickets.
- `read_event(session, current_user, id) -> EventDetail` — 404 when missing; inserts the seen link once; returns tickets.
- `set_event_bookmark(session, current_user, id, body: EventBookmarkUpdate) -> EventPublic` — sets or clears the link; 404 when missing; no tickets.
- `create_event(session, current_user, event_in: EventCreate) -> EventPublic` — maps `LookupError` to 404 and `ValueError` to 400; response has no tickets.
- `update_event(session, current_user, id, event_in: EventUpdate) -> EventPublic` — owner or superuser; 404 or 403 otherwise.
- `delete_event(session, current_user, id) -> Message` — owner or superuser; tickets and links go with the event.

Afterward, grep `backend/` for `Item`, `create_item`, and `/items`. Remaining hits belong only in older Alembic revisions. Do not edit those.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_create_event.py tests/api/routes/test_events.py tests/api/routes/test_users.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

Stage only the files listed for this task, including the deletions of `items.py`, `tests/utils/item.py`, and `test_items.py`. Commit message: `Replace items with events, venues, performers, and tickets.`

---

### Task 2: Seed one event from init_db

**Files:**
- Modify: `backend/app/core/db.py`
- Modify: `backend/tests/api/routes/test_events.py`
- Test: `backend/tests/api/routes/test_events.py::test_seed_opening_night`

**Interfaces:**

- `init_db(session) -> None` — after the first superuser exists, if no venue is named `Main Hall`, insert that venue, `The Band`, and call `crud.create_event` for `Opening Night` at price `25.0`.

- [ ] **Step 1: Write the failing test**

`test_seed_opening_night` — `GET /events/` includes `Opening Night` with no `tickets` key; `GET /events/{id}` returns 21 tickets, and `(0, 2)` is `25.0`, `AVAILABLE`, `user_id` null.

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && uv run pytest tests/api/routes/test_events.py::test_seed_opening_night -v`

Expected: FAIL because no event is named `Opening Night`.

- [ ] **Step 3: Seed from init_db**

Keep table creation on Alembic. Do not call `SQLModel.metadata.create_all`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_create_event.py tests/api/routes/test_events.py tests/api/routes/test_users.py -v`

Expected: PASS, including `test_seed_opening_night`. The session fixture already calls `init_db`. Cleanup still deletes events before venues.

- [ ] **Step 5: Commit**

Stage `backend/app/core/db.py` and `backend/tests/api/routes/test_events.py`. Commit message: `Seed a Main Hall event through the shared ticket writer.`
