# Microservice Architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the single FastAPI app with an API Gateway, a User CRUD Service, and an Event CRUD Service, and move user-delete, seed, and creator refresh onto a Redis stream.

**Architecture:** The gateway owns the public `/api/v1` routes and forwards the path, query, and body unchanged. The User CRUD Service writes an outbox row in the same transaction as a user create, display-name change, or delete. A publisher loop appends that row to Redis. The Event CRUD Service consumes the stream and never reads the user table. One Postgres database holds both schemas, with two Alembic version tables. `backend/` is deleted only after the three services and the frontend pass.

**Tech Stack:** FastAPI, SQLModel, Alembic, Pydantic, Postgres, Redis streams, httpx, pytest, the existing uv workspace, Docker Compose, Playwright.

**Spec:** `docs/superpowers/specs/2026-09-22-microservice-architecture-design.md`

## Global Constraints

- Public prefix `/api/v1`. No trailing slashes. Gateway strips that prefix and forwards the rest. It does not reshape bodies and does not forward the client's `Authorization` header.
- Header `X-Internal-Key` on every service call. Protected forwards also send `X-Caller`, the base64 of the UTF-8 JSON caller (`id`, `is_active`, `is_superuser`, `display_name`). `display_name` is `full_name` when that string is non-empty, otherwise `email`.
- A bad internal key or a missing caller is `401` from the service. The gateway turns service `401`, and any connection failure, into `503` with detail `Service unavailable`. A forward or resolve that exceeds 10 seconds is `504` with detail `Gateway timeout`, and a timed-out resolve is not forwarded. Every other `4xx`, including `422`, is forwarded unchanged.
- Invalid or missing bearer token, and a token whose user row is missing: `403`, detail `Could not validate credentials`. Inactive user: `400`, detail `Inactive user`.
- Redis stream `user-events`, dead stream `user-events-dead`, consumer group `event-crud`. Stream field name is `data`. The JSON value is `{"event_name": "<name>", "payload": { ... }}`.
- Messages: `UserCreated` (`id`, `display_name`, `is_superuser`), `UserUpdated` (`id`, `display_name`), `UserDeleted` (`id`). Password changes and `is_active` / `is_superuser` changes publish nothing. A rejected request writes no outbox row.
- A failed consumer delivery is not acknowledged. On the 5th delivery (`times_delivered >= 5`) the payload is appended to `user-events-dead` and the original is acknowledged. Handlers are safe to run twice.
- Alembic version tables: `alembic_version_user_crud` and `alembic_version_event_crud`. New histories. The old `backend/app/alembic` chain is deleted in the cleanup task, not split. Databases are recreated. No creator backfill.
- `GET /health` on each domain service returns `true` and needs no key. Gateway `GET /api/v1/health` returns `true` only when both do.
- `POST /dev/users` exists only when `FASTAPI_ENV=development`.
- Venue and performer have no public routes. Event behavior stays the event schema spec: list newest `created_at` first, bookmarked list, detail marks seen and includes tickets, bookmark body `{ "is_bookmarked": bool }`, create writes one `AVAILABLE` ticket per seat, update changes `name`, `description`, `time`, `performer_id` only, delete is owner or superuser.
- Error strings that stay: `Incorrect email or password`, `If that email is registered, we sent a password recovery link`, `Invalid token`, `Password updated successfully`, `The user with this email already exists in the system` (public signup, `400`), `User with this email already exists` (`409`), `Incorrect password`, `New password cannot be the same as the current one`, `Super users are not allowed to delete themselves`, `The user doesn't have enough privileges`, `User not found`, `The user with this id does not exist in the system`, `User deleted successfully`, `Event not found`, `Not enough permissions`, `Venue not found`, `Performer not found`, `Invalid seat map`, `Event deleted successfully`. Admin create of a duplicate email is `409` with `User with this email already exists` (today's handler returns `400`; do not keep that).
- Seed, only when `UserCreated.is_superuser` is true and no venue is named `Main Hall`: venue `Main Hall` / `Tel Aviv` / `Israel` / `[4, 5, 5, 7]`; performer `The Band` / `MUSIC` / `Live music`; event `Opening Night` / `First show of the season` / `2026-10-01T20:00:00Z` / price `25.0`, `owner_id` and `creator` from the message. Ticket generation stays inside `create_event`. `LookupError` and `ValueError` stay. No service class, repository, or custom exception type.
- Coverage fail-under stays 90 for the User CRUD Service and the Event CRUD Service. The gateway suite has no coverage floor.
- `git add` only the files named in that task. The worktree has unrelated untracked files. Do not stage them.
- Do not add a dependency other than the Redis client `redis>=5.0,<7` on the two domain services.

## File structure

- Create `packages/contracts/` — public Pydantic models, caller codec, and the three message payloads. No SQLModel tables and no FastAPI app.
- Create `services/user-crud/` — users, login, password reset, email, outbox, publisher loop. Tables: `user`, `outbox`.
- Create `services/event-crud/` — events, venues, performers, tickets, seen, bookmarks, consumer loop. No user table.
- Create `services/gateway/` — public routes, token resolution, forwarder, built-frontend hosting. No database and no Redis.
- Modify `pyproject.toml` — uv workspace members gain the new packages, then lose `backend` in the cleanup task.
- Modify `compose.yml`, `compose.override.yml`, `compose.deploy.yml` — replace the `backend` service with `gateway`, `user-crud`, `event-crud`, and `redis`.
- Modify `.github/workflows/test-backend.yml`, `test-docker-compose.yml`, `playwright.yml`, `deploy.yml`, `deploy-docker-compose.yml`, `smokeshow.yml` — point at the three services.
- Modify `scripts/generate-client.sh`, `frontend` call sites, and `frontend/tests` — client comes from the gateway spec.
- Delete `backend/` in the last task, after nothing imports it.

Each service keeps the import package name `app` and is tested from its own directory, the way `backend/` is today. They import `contracts`. They do not import each other.

---

### Task 1: Shared contracts

**Files:**
- Create: `packages/contracts/pyproject.toml`
- Create: `packages/contracts/contracts/__init__.py`
- Create: `packages/contracts/contracts/caller.py`
- Create: `packages/contracts/contracts/messages.py`
- Create: `packages/contracts/contracts/users.py`
- Create: `packages/contracts/contracts/events.py`
- Create: `packages/contracts/tests/test_caller.py`
- Create: `packages/contracts/tests/test_messages.py`
- Modify: `pyproject.toml` — workspace member `packages/contracts`
- Test: `packages/contracts/tests/test_caller.py`, `packages/contracts/tests/test_messages.py`

**Interfaces:**
- Consumes: nothing
- Produces:
  - `Caller(id: UUID, is_active: bool, is_superuser: bool, display_name: str)`
  - `encode_caller(caller: Caller) -> str` and `decode_caller(value: str) -> Caller`. `decode_caller` raises `ValueError` on bad base64 or a body that is not a caller.
  - `INTERNAL_KEY_HEADER = "X-Internal-Key"`, `CALLER_HEADER = "X-Caller"`
  - `UserCreated`, `UserUpdated`, `UserDeleted` with the fields in Global Constraints
  - `UserMessage(event_name: Literal["UserCreated", "UserUpdated", "UserDeleted"], payload: UserCreated | UserUpdated | UserDeleted)`
  - `dump_message(message: UserMessage) -> str` and `load_message(data: str) -> UserMessage`. UUIDs are JSON strings. `load_message` raises `ValueError` on an unknown `event_name` or a payload that does not match.
  - `STREAM = "user-events"`, `DEAD_STREAM = "user-events-dead"`, `CONSUMER_GROUP = "event-crud"`
  - User API models moved off SQLModel tables: `LoginRequest(email, password)`, `UserCreate`, `UserRegister`, `UserUpdate`, `UserUpdateMe`, `UpdatePassword`, `UserPublic`, `UsersPublic`, `Token`, `NewPassword`, `Message`. Field limits match `backend/app/models.py`. `LoginRequest.password` is only required to be non-empty, so a wrong password stays `400` rather than `422`.
  - Event API models: `EventCreate`, `EventUpdate`, `EventPublic`, `EventDetail`, `EventBookmarkUpdate`, `EventsPublic`, `TicketPublic`, `TicketAvailability`, `PerformerGenre`. `EventPublic.creator` is a required string on the model. There is no `from_event` and no owner relationship.

- [ ] **Step 1: Write the failing tests**

`test_caller.py`: round-trip a caller whose `display_name` is `José`. Assert `decode_caller` of garbage raises `ValueError`.

`test_messages.py`: round-trip one of each message through `dump_message` and `load_message`. Assert `load_message` of `{"event_name": "NoSuch", "payload": {}}` raises `ValueError`.

- [ ] **Step 2: Run the tests to verify they fail**

Run from the repo root: `uv run --package contracts pytest packages/contracts/tests -v`

Expected: FAIL because the package does not exist yet.

- [ ] **Step 3: Implement the package**

Pydantic models only. `encode_caller` is the base64 of `Caller` JSON in UTF-8. Export the names above from `contracts/__init__.py`. Package depends on `pydantic` only. Add the workspace member and run `uv lock` from the repo root.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run --package contracts pytest packages/contracts/tests -v`

Expected: PASS

- [ ] **Step 5: Commit**

Stage only the contracts package, `pyproject.toml`, and `uv.lock`. Message: `Add shared caller, message, and API models.`

---

### Task 2: User CRUD service skeleton

**Files:**
- Create: `services/user-crud/pyproject.toml`
- Create: `services/user-crud/alembic.ini`
- Create: `services/user-crud/app/main.py`
- Create: `services/user-crud/app/models.py`
- Create: `services/user-crud/app/core/config.py`
- Create: `services/user-crud/app/core/db.py`
- Create: `services/user-crud/app/api/routes/health.py`
- Create: `services/user-crud/app/alembic/env.py`
- Create: `services/user-crud/app/alembic/versions/c4e8a1b92d10_create_user_and_outbox.py`
- Create: `services/user-crud/tests/conftest.py`
- Create: `services/user-crud/tests/test_health.py`
- Create: `services/user-crud/tests/test_migration.py`
- Modify: `pyproject.toml` — workspace member `services/user-crud`
- Test: `services/user-crud/tests/test_health.py`, `services/user-crud/tests/test_migration.py`

**Interfaces:**
- Consumes: `contracts` (not required at runtime yet; the dependency is declared so later tasks can import it)
- Produces:
  - Table `user` with the current columns (`id`, `email`, `is_active`, `is_superuser`, `full_name`, `hashed_password`, `created_at`) and no relationship to events
  - Table `outbox` (`id` UUID, `event_name` string, `payload` JSON, `created_at` timezone-aware, `published_at` timezone-aware nullable)
  - `GET /health` returns `true`
  - Settings: the current user, JWT, SMTP, and database settings from `backend/app/core/config.py`, plus `REDIS_URL` (default `redis://localhost:6379/0`) and `INTERNAL_API_KEY`
  - Alembic `version_table` is `alembic_version_user_crud` in both offline and online `context.configure`
  - `conftest.py` follows `backend/tests/conftest.py`: rewrite `DATABASE_URL` to database `app_test`, upgrade this service's Alembic head, yield a session. Do not create the first superuser in this task.

- [ ] **Step 1: Write the failing tests**

`test_health.py`: `TestClient` `GET /health` is `200` and the JSON body is `true`.

`test_migration.py`: after the session fixture, `user` and `outbox` exist, and `alembic_version_user_crud` has one row. Do not assert that `event` is absent. Later event tests share `app_test` and may have created it.

- [ ] **Step 2: Run the tests to verify they fail**

Run from `services/user-crud`: `uv run pytest tests/test_health.py tests/test_migration.py -v`

Expected: FAIL, package or tables missing. Postgres must be up (`docker compose up -d db`).

- [ ] **Step 3: Implement the skeleton**

Copy the backend project metadata (Python `>=3.14,<4`, ruff, mypy, coverage `source = ["app"]`, `[tool.fastapi] entrypoint = "app.main:app"`, fail-under is not enforced in this task's command). Dependencies: the current backend runtime deps plus `contracts` as a workspace dependency and `redis>=5.0,<7`. Drop nothing that email and JWT need. `app/main.py` includes only the health router. The migration creates `user` and `outbox` and downgrade drops `outbox` then `user`. Add the workspace member and `uv lock`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_health.py tests/test_migration.py -v` from `services/user-crud`

Expected: PASS

- [ ] **Step 5: Commit**

Message: `Add the User CRUD service skeleton and its tables.`

---

### Task 3: Auth routes and the outbox write

**Files:**
- Create: `services/user-crud/app/crud.py`
- Create: `services/user-crud/app/core/security.py`
- Create: `services/user-crud/app/email.py`
- Create: `services/user-crud/app/outbox.py`
- Create: `services/user-crud/app/api/deps.py`
- Create: `services/user-crud/app/api/routes/auth.py`
- Create: `services/user-crud/app/email-templates/` — copy of `backend/app/email-templates/`
- Create: `services/user-crud/tests/api/test_auth.py`
- Create: `services/user-crud/tests/test_outbox.py`
- Modify: `services/user-crud/app/main.py`
- Modify: `services/user-crud/tests/conftest.py` — fixture that sends `X-Internal-Key`
- Test: `services/user-crud/tests/api/test_auth.py`, `services/user-crud/tests/test_outbox.py`

**Interfaces:**
- Consumes: `Caller` is not used yet. `UserCreate`, `UserRegister`, `Token`, `NewPassword`, `Message`, `LoginRequest` from `contracts`. `INTERNAL_KEY_HEADER`.
- Produces:
  - `display_name(user) -> str`
  - `write_outbox(session, message: UserMessage) -> None` adds the row and does not commit
  - `require_internal_key` dependency: missing or wrong key is `401` detail `invalid internal key`
  - `POST /auth/login` function `login`. Body `LoginRequest`. Returns `Token`. Unknown email or bad password: `400` `Incorrect email or password`, and still runs the dummy hash the way `authenticate` does today. Inactive: `400` `Inactive user`.
  - `POST /auth/register` function `register`. Duplicate email: `400` `The user with this email already exists in the system`. Success writes `UserCreated` in the same commit as the user row.
  - `POST /auth/password-recovery` function `recover_password`. Body `{ "email": str }`. Always `200` with `If that email is registered, we sent a password recovery link`. Sends mail only when the user exists. No outbox row.
  - `POST /auth/reset-password` function `reset_password`. Invalid or unknown token: `400` `Invalid token`. Success message `Password updated successfully`. No outbox row.
  - Copy `create_user`, `update_user`, `get_user_by_email`, `authenticate` from `backend/app/crud.py`. Do not copy `create_event`.
  - Copy password hashing and token helpers from `backend/app/core/security.py` and the email helpers from `backend/app/utils.py` except `generate_test_email`. Template path stays next to the email module.

- [ ] **Step 1: Write the failing tests**

`test_auth.py`, all requests send the test internal key. A second request with the wrong key is `401`.

Login success returns a bearer token. Login failure is `400` and does not write `outbox`. Inactive user is `400` `Inactive user`.

Register writes one `outbox` row with `event_name` `UserCreated`, payload `id` equal to the new user, `display_name` equal to the email when `full_name` is omitted, and `is_superuser` false. Duplicate register is `400` and adds no second outbox row.

Password recovery for an unknown email still returns the same message. Reset with a bad token is `400` and writes no outbox row.

`test_outbox.py`: `write_outbox` without `commit` is invisible to a second session. After the caller's commit, the row is there with `published_at` null.

- [ ] **Step 2: Run the tests to verify they fail**

Run from `services/user-crud`: `uv run pytest tests/api/test_auth.py tests/test_outbox.py -v`

Expected: FAIL, routes missing.

- [ ] **Step 3: Implement auth and outbox writes**

Mount `auth.router` at the app root (the router prefix is `/auth`). Every auth route depends on `require_internal_key`. Do not start a Redis loop in this task.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/api/test_auth.py tests/test_outbox.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

Message: `Serve login and register from the User CRUD service.`

---

### Task 4: User routes, dev create, and token resolution

**Files:**
- Create: `services/user-crud/app/api/routes/users.py`
- Create: `services/user-crud/app/api/routes/internal.py`
- Create: `services/user-crud/app/api/routes/dev.py`
- Create: `services/user-crud/app/initial_data.py`
- Create: `services/user-crud/tests/api/test_users.py`
- Create: `services/user-crud/tests/api/test_resolve_token.py`
- Create: `services/user-crud/tests/api/test_dev.py`
- Modify: `services/user-crud/app/main.py`
- Modify: `services/user-crud/app/api/deps.py`
- Modify: `services/user-crud/app/core/db.py` — `init_db` creates the first superuser only
- Modify: `services/user-crud/tests/conftest.py` — call `init_db`, add a caller-header helper
- Test: `services/user-crud/tests/api/test_users.py`, `services/user-crud/tests/api/test_resolve_token.py`, `services/user-crud/tests/api/test_dev.py`

**Interfaces:**
- Consumes: `write_outbox`, `display_name`, `require_internal_key`, `encode_caller`, `decode_caller`, `Caller`
- Produces:
  - `require_caller` reads `X-Caller`. Missing or undecodable is `401` `missing caller`. `is_active` false is `400` `Inactive user`. Returns `Caller`.
  - `require_superuser` depends on `require_caller`. False `is_superuser` is `403` `The user doesn't have enough privileges`.
  - `POST /internal/resolve-token` function `resolve_token`. Body `{ "token": str }`. Internal key required, no caller. Returns `Caller`. Missing user and bad token are `403` `Could not validate credentials`. Inactive is `400` `Inactive user`. This route is not mounted on the gateway later.
  - User routes, function names kept so the generated client methods stay `readUsers`, `createUser`, `updateUserMe`, `updatePasswordMe`, `readUserMe`, `deleteUserMe`, `readUserById`, `updateUser`, `deleteUser`:
    - `GET /users` and `POST /users` and `PATCH /users/{user_id}` and `DELETE /users/{user_id}` require a superuser caller
    - `GET /users/me`, `PATCH /users/me`, `PATCH /users/me/password`, `DELETE /users/me`, `GET /users/{user_id}` require a caller
    - `POST /users` duplicate email is `409` `User with this email already exists` and writes `UserCreated` only on success
    - `PATCH /users/me` and `PATCH /users/{user_id}` write `UserUpdated` only when `display_name` changes
    - `PATCH /users/me/password` never writes an outbox row
    - `DELETE /users/me` and `DELETE /users/{user_id}` write `UserDeleted` in the same commit as the delete. They do not import `Event` and do not delete event rows
    - Superuser self-delete is `403` `Super users are not allowed to delete themselves` and writes nothing
  - `POST /dev/users` function `create_user`, tag `dev`, included only when `FASTAPI_ENV=development`. No caller. Body is the current private-create shape (`email`, `password`, `full_name`, `is_verified` ignored). Writes `UserCreated`.
  - `init_db(session)` creates the first superuser when missing and writes `UserCreated` with `is_superuser` true in that same commit. It does not touch venues or events.

- [ ] **Step 1: Write the failing tests**

`test_resolve_token.py`: a token from `POST /auth/login` resolves to that user's id, `is_superuser`, and `display_name`. A garbage token is `403`. An inactive user is `400`.

`test_users.py` sends the internal key plus `encode_caller` for a caller built from a real user row. Cover: me, list forbidden to a normal caller (`403`), admin create `409` on duplicate email, display-name change writes one `UserUpdated`, email change that leaves `display_name` the same writes nothing, password change writes nothing, delete writes one `UserDeleted` and removes the user row, superuser self-delete writes nothing.

`test_dev.py`: with `FASTAPI_ENV=development`, `POST /dev/users` returns the user and one `UserCreated` row. No bearer token.

- [ ] **Step 2: Run the tests to verify they fail**

Run from `services/user-crud`: `uv run pytest tests/api/test_users.py tests/api/test_resolve_token.py tests/api/test_dev.py -v`

Expected: FAIL, routes missing.

- [ ] **Step 3: Implement the routes**

`init_db` runs from the session fixture so the first superuser exists for login. Include `dev.router` only in development, same pattern as today's private router in `backend/app/api/main.py`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/api/test_users.py tests/api/test_resolve_token.py tests/api/test_dev.py tests/api/test_auth.py -v`

Expected: PASS, including the earlier auth tests.

- [ ] **Step 5: Commit**

Message: `Add user routes and token resolution without touching events.`

---

### Task 5: Outbox publisher

**Files:**
- Create: `services/user-crud/app/publisher.py`
- Create: `services/user-crud/tests/test_publisher.py`
- Modify: `services/user-crud/app/main.py` — start the loop on lifespan
- Test: `services/user-crud/tests/test_publisher.py`

**Interfaces:**
- Consumes: `write_outbox`, `dump_message`, `STREAM`
- Produces:
  - `publish_pending(redis) -> int` loads rows with `published_at` null, appends `dump_message` as stream field `data`, then sets `published_at`. Returns how many rows it published. A Redis error leaves `published_at` null and does not raise out of the loop.
  - `run_publisher()` calls `publish_pending` about once a second until cancelled. The FastAPI lifespan starts it. Startup still serves HTTP when Redis is down.

- [ ] **Step 1: Write the failing test**

Requires Redis at `redis://localhost:6379/0`. Run `docker run --rm -p 6379:6379 redis:7` when Compose does not have Redis yet. Insert one unpublished `UserDeleted` via `write_outbox` and commit. Call `publish_pending`. Assert the return is `1`, `published_at` is set, and `XRANGE` on `user-events` contains that payload. Call it again and assert the return is `0`.

- [ ] **Step 2: Run the test to verify it fails**

Run from `services/user-crud`: `uv run pytest tests/test_publisher.py -v`

Expected: FAIL, `publish_pending` missing.

- [ ] **Step 3: Implement the publisher**

Use the `redis` client. One stream append per row. Set `published_at` only after that append returns. The lifespan task logs and retries when Redis refuses the connection.

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/test_publisher.py tests/api/test_auth.py -v`

Expected: PASS. Auth tests still pass with Redis down or up, because they do not call `publish_pending`.

- [ ] **Step 5: Commit**

Message: `Publish user outbox rows to Redis.`

---

### Task 6: Event CRUD tables and create_event

**Files:**
- Create: `services/event-crud/pyproject.toml`
- Create: `services/event-crud/alembic.ini`
- Create: `services/event-crud/app/main.py`
- Create: `services/event-crud/app/models.py`
- Create: `services/event-crud/app/crud.py`
- Create: `services/event-crud/app/core/config.py`
- Create: `services/event-crud/app/core/db.py`
- Create: `services/event-crud/app/api/routes/health.py`
- Create: `services/event-crud/app/alembic/env.py`
- Create: `services/event-crud/app/alembic/versions/d5f9b2c03e21_create_event_tables.py`
- Create: `services/event-crud/tests/conftest.py`
- Create: `services/event-crud/tests/test_create_event.py`
- Create: `services/event-crud/tests/utils/event.py`
- Modify: `pyproject.toml` — workspace member `services/event-crud`
- Test: `services/event-crud/tests/test_create_event.py`

**Interfaces:**
- Consumes: `EventCreate`, `TicketAvailability`, `PerformerGenre` from `contracts`
- Produces:
  - Tables `venue`, `performer`, `event`, `ticket`, `eventreadlink`, `eventbookmarklink` in their final shape. `event.creator` is a required string. `event.owner_id`, `ticket.user_id`, and both link `user_id` columns are UUIDs with no foreign key to `user`. `ticket.user_id` is nullable. Venue and performer foreign keys stay `ON DELETE RESTRICT`. Ticket and link foreign keys to `event` stay `ON DELETE CASCADE`. Unique `(event_id, row, seat)`. Checks: `price >= 0`, `row >= 0`, `seat >= 0`. Enum type names `performer_genre` and `ticket_availability`.
  - `create_event(session, event_in: EventCreate, owner_id: UUID, creator: str) -> Event`. Same ticket rules as `backend/app/crud.py`. Stores `creator` on the row. Raises `LookupError("Venue")`, `LookupError("Performer")`, or `ValueError("Invalid seat map")`. One commit.
  - `GET /health` returns `true`
  - Settings: `DATABASE_URL`, `REDIS_URL`, `INTERNAL_API_KEY`, `SENTRY_DSN`, `FASTAPI_ENV`. No SMTP and no `SECRET_KEY`.
  - Alembic `version_table` is `alembic_version_event_crud`
  - `conftest.py` upgrades this history on `app_test` and deletes tickets, links, events, performers, and venues at the end of the session. It does not delete `user` rows.
  - `create_random_event(db, *, creator: str, owner_id: UUID) -> Event` — seat map `[1]`, price `10.0`

- [ ] **Step 1: Write the failing test**

Port the assertions in `backend/tests/test_create_event.py`. A seat map `[4, 5, 5, 7]` writes 21 tickets at the request price, `availability` `AVAILABLE`, `user_id` null, and the 3rd seat of the 1st row is `(0, 2)`. The event's `creator` is the argument, not a joined user. Missing venue raises `LookupError`. An empty seat map raises `ValueError` and leaves no event row. `GET /health` is `true`.

- [ ] **Step 2: Run the test to verify it fails**

Run from `services/event-crud`: `uv run pytest tests/test_create_event.py -v`

Expected: FAIL, package missing.

- [ ] **Step 3: Implement models, migration, and create_event**

Dependencies: FastAPI, SQLModel, Alembic, psycopg, pydantic-settings, sentry, `contracts`, `redis>=5.0,<7`. `[tool.fastapi] entrypoint = "app.main:app"`. No email and no JWT libraries. No `User` class and no relationship aimed at `user`. Add the workspace member and `uv lock`.

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/test_create_event.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

Message: `Add event tables and ticket creation without a user foreign key.`

---

### Task 7: Event HTTP routes

**Files:**
- Create: `services/event-crud/app/api/deps.py`
- Create: `services/event-crud/app/api/routes/events.py`
- Create: `services/event-crud/tests/api/test_events.py`
- Modify: `services/event-crud/app/main.py`
- Test: `services/event-crud/tests/api/test_events.py`

**Interfaces:**
- Consumes: `create_event`, `encode_caller`, `Caller`, `INTERNAL_KEY_HEADER`, `CALLER_HEADER`, event API models from `contracts`
- Produces:
  - `require_caller` same rules as the user service (`401` `missing caller`, `401` `invalid internal key`, `400` `Inactive user`)
  - `event_public(event, *, is_read: bool, is_bookmarked: bool) -> EventPublic` copies `event.creator` from the row. It does not load a user.
  - Routes and function names: `read_events` `GET /events`, `read_bookmarked_events` `GET /events/bookmarked`, `read_event` `GET /events/{id}`, `set_event_bookmark` `PUT /events/{id}/bookmark`, `create_event` `POST /events`, `update_event` `PUT /events/{id}`, `delete_event` `DELETE /events/{id}`. Tag `events`.
  - Create passes `caller.id` and `caller.display_name` into `crud.create_event`.
  - Update and delete: caller id must equal `owner_id` or `caller.is_superuser`, else `403` `Not enough permissions`. Missing event is `404` `Event not found`.
  - Detail marks seen by inserting `EventReadLink` when missing, and embeds tickets.
  - List order is `created_at` descending. Responses include `is_read` and `is_bookmarked` for the caller id.

- [ ] **Step 1: Write the failing tests**

Port `backend/tests/api/routes/test_events.py` to send the internal key and a caller instead of a bearer token. Assert create response `creator` equals the caller's `display_name`. A caller who is not the owner and not a superuser gets `403` on update and delete. Missing event is `404`. Bad seat map is `400` `Invalid seat map`. Unknown venue is `404` `Venue not found`. Bookmark then `GET /events/bookmarked` returns that event with `is_bookmarked` true. `GET /events/{id}` sets `is_read` true and includes one ticket per seat. A second get does not insert a second read link.

- [ ] **Step 2: Run the tests to verify they fail**

Run from `services/event-crud`: `uv run pytest tests/api/test_events.py -v`

Expected: FAIL, routes missing.

- [ ] **Step 3: Implement the routes**

Move the query helpers from `backend/app/api/routes/events.py` (`_link_event_ids`, list, bookmark, seen). Replace `_event_flags` usage and `EventPublic.from_event` with `event_public`. Do not import anything from `services/user-crud`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/api/test_events.py tests/test_create_event.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

Message: `Serve event routes from the Event CRUD service.`

---

### Task 8: User-event consumer

**Files:**
- Create: `services/event-crud/app/consumer.py`
- Create: `services/event-crud/tests/test_consumer.py`
- Modify: `services/event-crud/app/main.py` — start the loop on lifespan
- Test: `services/event-crud/tests/test_consumer.py`

**Interfaces:**
- Consumes: `create_event`, `UserMessage`, `load_message`, `STREAM`, `DEAD_STREAM`, `CONSUMER_GROUP`
- Produces:
  - `apply_user_created(session, payload: UserCreated) -> None`. When `is_superuser` is true and no venue is named `Main Hall`, create the seed venue, performer, and event through `create_event` with `owner_id` and `creator` from the payload. Otherwise do nothing. A second call does nothing.
  - `apply_user_updated(session, payload: UserUpdated) -> None` sets `creator` on events whose `owner_id` equals `payload.id`.
  - `apply_user_deleted(session, payload: UserDeleted) -> None` deletes events with that `owner_id` (tickets and that event's links go with the row), deletes `eventreadlink` and `eventbookmarklink` rows with that `user_id`, and sets `ticket.user_id` to null where it matches. `availability` is left as stored. A second call changes nothing.
  - `outcome(handled: bool, times_delivered: int) -> Literal["ack", "retry", "dead"]`. Success is `ack`. Failure with `times_delivered < 5` is `retry`. Failure with `times_delivered >= 5` is `dead`.
  - `run_consumer()` ensures the group exists, reads new and pending messages, runs the matching handler, acknowledges only on `ack` or after appending to `user-events-dead` on `dead`. A Redis outage is logged and retried. The process still serves HTTP.

- [ ] **Step 1: Write the failing tests**

`test_consumer.py` calls the handlers with a session and does not need Redis for the row checks.

`UserCreated` for a superuser creates Main Hall, The Band, and Opening Night owned by that id with `creator` from the payload and 21 tickets. A non-superuser message does not. A second superuser message does not add a second Main Hall.

`UserUpdated` changes `creator` only on that owner's events.

`UserDeleted` removes owned events, removes that user's bookmark on someone else's event, nulls `ticket.user_id` on a ticket bought by them, and leaves `availability` unchanged. Running it again does not raise.

`outcome(True, 1)` is `ack`. `outcome(False, 4)` is `retry`. `outcome(False, 5)` is `dead`.

- [ ] **Step 2: Run the tests to verify they fail**

Run from `services/event-crud`: `uv run pytest tests/test_consumer.py -v`

Expected: FAIL, handlers missing.

- [ ] **Step 3: Implement the handlers and the loop**

Handlers commit their own transaction. `apply_user_created` uses `create_event` for Opening Night so the tickets and the event commit together. The lifespan starts `run_consumer`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_consumer.py tests/api/test_events.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

Message: `Apply user lifecycle messages inside the Event CRUD service.`

---

### Task 9: API gateway

**Files:**
- Create: `services/gateway/pyproject.toml`
- Create: `services/gateway/app/main.py`
- Create: `services/gateway/app/forward.py`
- Create: `services/gateway/app/core/config.py`
- Create: `services/gateway/app/api/auth.py`
- Create: `services/gateway/app/api/users.py`
- Create: `services/gateway/app/api/events.py`
- Create: `services/gateway/app/api/health.py`
- Create: `services/gateway/app/api/dev.py`
- Create: `services/gateway/tests/test_forward.py`
- Modify: `pyproject.toml` — workspace member `services/gateway`
- Test: `services/gateway/tests/test_forward.py`

**Interfaces:**
- Consumes: `encode_caller`, `Caller`, `INTERNAL_KEY_HEADER`, `CALLER_HEADER`, and the public models from `contracts`. User service `POST /internal/resolve-token`. Both services' public paths.
- Produces:
  - Settings: `PROJECT_NAME`, `FRONTEND_HOST`, `USER_CRUD_URL`, `EVENT_CRUD_URL`, `INTERNAL_API_KEY`, `SENTRY_DSN`, `FASTAPI_ENV`. No database URL, no SMTP, no `SECRET_KEY`.
  - `resolve_caller(token: str) -> Caller` posts the token to `{USER_CRUD_URL}/internal/resolve-token` with the internal key and a 10 second timeout. Returns the caller on `200`. Forwards `400` and `403` detail to the client. Timeout is `504`. Connection failure and `401` are `503`.
  - `forward(method, path, query, body, *, service_url, caller: Caller | None) -> Response` calls `{service_url}{path}` with the internal key, `X-Caller` only when `caller` is not None, no `Authorization` header, and the same timeout. `401` becomes `503`. Other statuses, including the body, pass through. Timeout is `504`.
  - Gateway routes use the same function names as the services so operation ids stay stable: auth `login`, `register`, `recover_password`, `reset_password`; users as in Task 4; events as in Task 7; dev `create_user`. OpenAPI tags `auth`, `users`, `events`, and `dev` in development. Security scheme is HTTP Bearer. Login body is `LoginRequest`, not a form.
  - Auth routes and `POST /dev/users` call `forward` with `caller=None`. Every other route calls `resolve_caller` first. Missing `Authorization` is `403` `Could not validate credentials`.
  - `GET /api/v1/health` function `health_check` GETs `{USER_CRUD_URL}/health` and `{EVENT_CRUD_URL}/health`. Both `200` returns `true`. Anything else is `503`.
  - When directory `app/frontend` exists, serve it at `/`, the way `backend/app/main.py` does.
  - The httpx client is constructed in one function the tests replace with a mock transport. Tests do not open a port.

- [ ] **Step 1: Write the failing tests**

`test_forward.py` uses a mock transport and no database.

Missing token on `GET /api/v1/users/me` is `403` and the mock records no outbound request.

A resolve response `403` `Could not validate credentials` is returned as that status and detail, and the events service is not called.

A resolve response `400` `Inactive user` is returned as that, and the events service is not called.

A resolve connection error is `503` `Service unavailable`.

A resolve that exceeds the timeout is `504` `Gateway timeout`.

A successful resolve of a caller, then `POST /api/v1/events` with body `{"name": "Show"}`, records an event-service request whose path is `/events`, whose body is that same JSON, whose headers include `X-Internal-Key` and `X-Caller` equal to `encode_caller` of the resolved caller, and whose headers omit `Authorization`.

An event-service `401` becomes `503`. An event-service `404` `Event not found` is forwarded as `404` with that detail.

`GET /api/v1/health` is `true` when both health calls are `200`, and `503` when the event health call fails.

`POST /api/v1/auth/login` forwards to `/auth/login` with no `X-Caller`.

With `FASTAPI_ENV=development`, the OpenAPI document contains `/api/v1/dev/users` and does not contain `/internal/resolve-token`.

- [ ] **Step 2: Run the tests to verify they fail**

Run from `services/gateway`: `uv run pytest tests/test_forward.py -v`

Expected: FAIL, app missing.

- [ ] **Step 3: Implement the gateway**

Dependencies: FastAPI, httpx, pydantic-settings, sentry, `contracts`. `[tool.fastapi] entrypoint = "app.main:app"`. No Redis, no SQLModel, no PyJWT. Add the workspace member and `uv lock`. CORS stays as in `backend/app/main.py` (`FRONTEND_HOST`, credentials, all methods and headers).

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_forward.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

Message: `Forward public routes through the API gateway.`

---

### Task 10: Compose, Docker, and CI

**Files:**
- Create: `services/user-crud/Dockerfile`
- Create: `services/user-crud/scripts/prestart.sh`
- Create: `services/event-crud/Dockerfile`
- Create: `services/event-crud/scripts/prestart.sh`
- Create: `services/gateway/Dockerfile`
- Modify: `compose.yml`
- Modify: `compose.override.yml`
- Modify: `compose.deploy.yml`
- Modify: `.env.example`
- Modify: `.github/workflows/test-backend.yml`
- Modify: `.github/workflows/test-docker-compose.yml`
- Modify: `.github/workflows/playwright.yml`
- Modify: `.github/workflows/deploy-docker-compose.yml`
- Modify: `.github/workflows/smokeshow.yml`
- Modify: `development.md`
- Test: the three pytest suites and `curl` against the gateway health path

**Interfaces:**
- Consumes: the three apps and both Alembic heads
- Produces:
  - Compose services `redis` (image `redis:7`), `user-crud`, `event-crud`, and `gateway`. No published ports on the two domain services. Traefik labels that today sit on `backend` move onto `gateway` only. `gateway` depends on both domain services being healthy.
  - Domain healthcheck: `curl -f http://localhost:8000/health`. Gateway healthcheck: `curl -f http://localhost:8000/api/v1/health`.
  - Env: both domain services get `DATABASE_URL`, `REDIS_URL=redis://redis:6379/0`, and `INTERNAL_API_KEY`. User service also gets the current SMTP and first-superuser variables. Gateway gets `USER_CRUD_URL=http://user-crud:8000`, `EVENT_CRUD_URL=http://event-crud:8000`, `INTERNAL_API_KEY`, `FRONTEND_HOST`, `PROJECT_NAME`. Gateway does not get `SECRET_KEY` or `DATABASE_URL`.
  - `.env.example` gains `INTERNAL_API_KEY=changethis` and `REDIS_URL=redis://localhost:6379/0`.
  - Dockerfiles follow `backend/Dockerfile` but `uv sync --package` uses `user-crud`, `event-crud`, or `gateway`. Build context is the repo root. Only the gateway image builds the frontend and copies it to `app/frontend`.
  - `prestart.sh` in each domain service runs `alembic upgrade head`. The user script also runs `python app/initial_data.py`.
  - Local override publishes gateway `8000:8000`, redis `6379:6379`, and sets `FASTAPI_ENV=development` on user-crud and gateway. Playwright service `depends_on` gateway, with `PLAYWRIGHT_BASE_URL` and `VITE_API_URL` set to `http://gateway:8000`.
  - `test-backend.yml` starts `db`, `redis`, and `mailpit`, then from each service directory runs coverage pytest and `coverage report --fail-under=90` for user-crud and event-crud. Gateway pytest runs with no fail-under. Artifacts: `services/user-crud/htmlcov` and `services/event-crud/htmlcov`.
  - `test-docker-compose.yml` runs both prestars, then `up -d --wait gateway adminer`, then curls `http://localhost:8000/api/v1/health` and `http://localhost:8000`.
  - `playwright.yml` path filter includes `services/**` and `packages/contracts/**` and drops `backend/**`. `uv sync` runs at the repo root. Prestart is the two service scripts. Compose starts `gateway` instead of `backend`.
  - `deploy-docker-compose.yml` env gains `INTERNAL_API_KEY` and `REDIS_URL`. The prepare step runs the user-crud prestart and then the event-crud prestart.
  - `smokeshow.yml` uploads `services/user-crud/htmlcov`. The event report stays the test-workflow artifact.
  - `development.md` describes `docker compose up -d db redis mailpit`, then the two prestars, then the three `fastapi dev` processes and Vite. `VITE_API_URL` is the gateway.

- [ ] **Step 1: Write the failing check**

There is no new pytest module. The check is the existing service suites plus the compose health curl, which fails until the services exist in Compose.

- [ ] **Step 2: Run the suites before Compose is wired**

From each service directory, run the full `uv run pytest -v`. Expected: the suites from Tasks 1–9 still PASS. `curl http://localhost:8000/api/v1/health` may fail until the stack is up. That is the red check for this task.

- [ ] **Step 3: Wire Compose, Dockerfiles, workflows, and development.md**

Remove the `backend` Compose service in this task so it no longer binds port `8000` or Traefik. Leave the `backend/` directory and the uv workspace member until Task 12. `test-backend.yml` runs the three new suites and stops calling `backend/scripts`.

- [ ] **Step 4: Run the stack**

`docker compose up -d --wait db redis mailpit gateway user-crud event-crud` after both prestars. `curl -f http://localhost:8000/api/v1/health` prints `true`. Then re-run the three pytest suites. User and event coverage reports meet 90. Gateway tests pass.

- [ ] **Step 5: Commit**

Message: `Run the gateway and both services from Compose.`

---

### Task 11: Frontend client and Playwright

**Files:**
- Modify: `scripts/generate-client.sh`
- Modify: `.pre-commit-config.yaml` — the generate-sdk hook file regex
- Modify: `frontend/src/hooks/useAuth.ts`
- Modify: `frontend/src/routes/login.tsx`
- Modify: `frontend/src/routes/recover-password.tsx`
- Modify: `frontend/src/routes/reset-password.tsx`
- Modify: `frontend/src/components/UserSettings/UserInformation.tsx`
- Modify: `frontend/src/components/UserSettings/ChangePassword.tsx`
- Modify: `frontend/src/components/UserSettings/DeleteConfirmation.tsx`
- Modify: `frontend/src/components/Admin/AddUser.tsx`
- Modify: `frontend/src/components/Admin/EditUser.tsx`
- Modify: `frontend/src/components/Admin/DeleteUser.tsx`
- Modify: `frontend/src/routes/_layout/admin.tsx`
- Modify: `frontend/tests/utils/privateApi.ts`
- Modify: `frontend/tests/auth.setup.ts`
- Modify: generated `frontend/openapi.json` and `frontend/src/client/`
- Test: `frontend/tests/auth.setup.ts` and `frontend/tests/events.spec.ts`

**Interfaces:**
- Consumes: gateway OpenAPI, tags `auth`, `users`, `events`, `dev`
- Produces:
  - `scripts/generate-client.sh` imports `app.main` from `services/gateway` with `FASTAPI_ENV=development`, writes `frontend/openapi.json`, and runs the existing `bun run --filter frontend generate-client`
  - Generated classes: `AuthService.login`, `AuthService.register`, `AuthService.recoverPassword`, `AuthService.resetPassword`, `UsersService` methods for the user routes, `EventsService` methods unchanged in name, `DevService.createUser`. No `LoginService`, `PrivateService`, or `UtilsService`.
  - `useAuth` login sends `{ email, password }` to `AuthService.login` and stores `access_token`. Signup calls `AuthService.register`. `readUserMe` stays on `UsersService`.
  - `login.tsx` submits `email` instead of `username`. The input keeps `data-testid="email-input"`.
  - `recover-password.tsx` sends `{ email }` to `AuthService.recoverPassword`. `reset-password.tsx` sends `{ token, new_password }` to `AuthService.resetPassword`.
  - `privateApi.ts` calls `DevService.createUser` on `/api/v1/dev/users`.
  - `auth.setup.ts` logs in as today, then polls `GET {VITE_API_URL}/api/v1/events` with the bearer token until some event is named `Opening Night`, for up to 20 seconds.
  - The pre-commit generate hook also runs when files under `services/gateway/`, `services/user-crud/app/`, `services/event-crud/app/`, or `packages/contracts/` change.

- [ ] **Step 1: Write the failing check**

Regenerate the client first in Step 3. The red check before that is `bun run --filter frontend lint` if you point `useAuth` at `AuthService` before generation: the import does not exist. Do the generation and the call-site edits in the same task, then lint.

- [ ] **Step 2: Generate the client**

Run: `bash scripts/generate-client.sh`

Expected: `frontend/src/client/index.ts` exports `AuthService`, `UsersService`, `EventsService`, and `DevService`.

- [ ] **Step 3: Update call sites and the Playwright setup poll**

Leave event components importing `EventsService`. Their method names stay. Update only the auth, user, and dev imports listed above.

- [ ] **Step 4: Verify**

Run: `bun run --filter frontend lint`

Then, with the stack up and both prestars already run: the Playwright setup project. Expected: login reaches `/` and the poll sees Opening Night.

Run: `bun run --filter frontend test` if the stack is up. Expected: existing Playwright specs pass. None of them assert that a deleted user's events disappear in the same step.

- [ ] **Step 5: Commit**

Message: `Point the frontend client at the gateway.`

---

### Task 12: Remove the monolith

**Files:**
- Delete: `backend/`
- Modify: `pyproject.toml` — drop workspace member `backend`
- Modify: `compose.yml`, `compose.override.yml`, `compose.deploy.yml` — delete the `backend` service
- Modify: `.pre-commit-config.yaml` — mypy and ty check `services/user-crud/app`, `services/event-crud/app`, `services/gateway/app`, and `packages/contracts/contracts`. End-of-file exclude points at `services/user-crud/app/email-templates/` instead of `backend/app/email-templates/`.
- Modify: `.github/workflows/deploy.yml` — prepare step runs user-crud `scripts/prestart.sh` and then event-crud `scripts/prestart.sh` with the cloud `DATABASE_URL`. `fastapi deploy` working directory becomes `services/gateway`. The cloud app still needs `USER_CRUD_URL`, `EVENT_CRUD_URL`, and `INTERNAL_API_KEY` in that environment; this task does not invent a cloud host for Redis or the workers.
- Modify: `.github/dependabot.yml` — docker directory `/backend` becomes `/services/gateway`, `/services/user-crud`, and `/services/event-crud`
- Modify: `.fastapicloudignore` — `!services/gateway/app/frontend/` instead of `!backend/app/frontend/`
- Modify: `README.md` — the backend doc link points at `services/user-crud` and `services/event-crud` only as a one-line replacement of the `backend/README.md` link. Do not rewrite the template marketing sections.
- Modify: `development.md` if any `backend` command remains
- Test: grep, then the three pytest suites and frontend lint

**Interfaces:**
- Consumes: Tasks 1–11 green
- Produces: no remaining import of `backend`, no route `/login/test-token`, no password-recovery HTML route, no `/utils/test-email`, no `generate_test_email`

- [ ] **Step 1: Confirm the new suites are green before deleting**

Run the three pytest suites and `bun run --filter frontend lint`. Expected: PASS. Do not delete `backend/` if any of those fail.

- [ ] **Step 2: Delete `backend/` and retarget the remaining config**

Search `services/`, `frontend/`, `scripts/`, `compose.yml`, `compose.override.yml`, `compose.deploy.yml`, `.github/`, and the root `pyproject.toml` for `backend/`, `LoginService`, `PrivateService`, `UtilsService`, `/login/test-token`, `test-email`, `password-recovery-html`, `generate_test_email`, and `from_event`. Fix or delete each hit. Leave the spec and this plan alone. Alembic files inside the deleted `backend/` tree disappear with it. Do not reintroduce a user foreign key or a direct HTTP call from the user service to the event service.

- [ ] **Step 3: Run the suites again**

Three pytest suites, coverage fail-under 90 on the two domain services, and `bun run --filter frontend lint`. Expected: PASS.

`uv run mypy services/user-crud/app services/event-crud/app services/gateway/app packages/contracts/contracts` and `uv run ty check` on those same paths. Expected: no errors.

- [ ] **Step 4: Commit**

Message: `Remove the monolithic backend.`

---

## Self-review notes

Spec sections and the task that covers them:

- Process split, caller header, and no cross-reads: Tasks 1, 4, 7, 9
- Outbox, Redis, publisher, consumer, dead letter, idempotent seed and purge: Tasks 3, 5, 8
- Public routes, removed routes, dev-only create, bearer login: Tasks 3, 4, 7, 9, 11
- Data ownership, two Alembic tables, `creator` column, no user foreign keys: Tasks 2 and 6
- Errors, including admin duplicate `409` and gateway `503` / `504`: Tasks 3, 4, 7, 9
- Tests, coverage, Playwright poll, local Compose: Tasks 5, 8, 10, 11
- Cleanup of `backend/` and the unused email helpers: Task 12

`deploy.yml` cannot host Redis and the two private services on FastAPI Cloud by itself. Task 12 migrates both schemas and deploys the gateway image, and it names the env vars that gateway process still needs. It does not add a cloud Redis.
