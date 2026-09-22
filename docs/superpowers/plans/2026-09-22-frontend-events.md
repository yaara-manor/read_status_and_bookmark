# Frontend Events Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the frontend call only `/events`, with pages, forms, and tests matching the event API that replaced items.

**Architecture:** Regenerate the OpenAPI client from the running backend so `ItemsService` and `/api/v1/items/` disappear and `EventsService` calls `/api/v1/events/`. Move the list and detail pages from `/items` to `/events`, and send `EventCreate` / `EventUpdate` fields instead of `title`. Do not add venue, performer, or ticket routes. The create form types `venue_id` and `performer_id`; Playwright copies those ids from the seeded Opening Night row on the events list.

**Tech Stack:** React 19, TanStack Router, TanStack Query, hey-api client (`scripts/generate-client.sh`), Playwright, existing FastAPI `/events` routes.

## Global Constraints

- Backend routes stay `/api/v1/events/`. Do not add `/venues`, `/performers`, `/tickets`, or put `/items` back.
- After this plan, frontend HTTP calls and in-app navigations use `/events` only. `/bookmarked` stays; it loads bookmarked events.
- List and bookmark responses are `EventPublic`: `id`, `name`, `description`, `time`, `venue_id`, `performer_id`, `owner_id`, `created_at`, `creator`, `is_read`, `is_bookmarked`. They have no `tickets`.
- `GET /events/{id}` is `EventDetail`: those fields plus `tickets` (`id`, `row`, `seat`, `price`, `availability`, `user_id`). Opening it marks the event seen.
- Create body is `name`, `description`, `venue_id`, `performer_id`, `time`, `price` (`>= 0`). `owner_id` is the logged-in user.
- Update body is optional `name`, `description`, `time`, `performer_id`. Do not send `venue_id` or `price`.
- Bookmark body stays `{ "is_bookmarked": bool }`.
- Missing event copy is `Event not found`. Create success copy is `Event created successfully`.
- Query key for the list is `["events"]`. Query key for one event is `["events", eventId]`. Bookmarked list key stays `["bookmarked"]`.
- Do not hand-edit `frontend/src/routeTree.gen.ts` or the generated files under `frontend/src/client/`. `scripts/generate-client.sh` rewrites the client. The Vite router plugin rewrites the route tree.
- Do not edit historical Alembic revisions.
- Seed used by tests: event `Opening Night` with `venue_id` and `performer_id` on `GET /api/v1/events/`.

## File structure

- Regenerate `frontend/openapi.json` and `frontend/src/client/` via `scripts/generate-client.sh`.
- Create `frontend/src/routes/_layout/events.tsx` (list) and `frontend/src/routes/_layout/events_.$eventId.tsx` (detail). Delete `frontend/src/routes/_layout/items.tsx` and `frontend/src/routes/_layout/items_.$itemId.tsx`.
- Create `frontend/src/components/Events/` by moving the Items components onto event types: `AddEvent`, `EditEvent`, `DeleteEvent`, `EventActionsMenu`, `EventsTable`, `columns`, `BookmarkToggle`. Delete `frontend/src/components/Items/`.
- Rename `frontend/src/components/Pending/PendingItems.tsx` to `PendingEvents.tsx` if nothing else imports it. Delete the old file.
- Modify `frontend/src/routes/_layout/bookmarked.tsx` and `frontend/src/components/Sidebar/AppSidebar.tsx`.
- Rename `frontend/tests/items.spec.ts` to `frontend/tests/events.spec.ts`. Delete the old spec.

---

### Task 1: Point the app at /events

**Files:**
- Modify: `frontend/src/client/` (generated), `frontend/openapi.json` (generated)
- Create: `frontend/src/routes/_layout/events.tsx`, `frontend/src/routes/_layout/events_.$eventId.tsx`, `frontend/src/components/Events/*`, `frontend/src/components/Pending/PendingEvents.tsx`, `frontend/tests/events.spec.ts`
- Modify: `frontend/src/routes/_layout/bookmarked.tsx`, `frontend/src/components/Sidebar/AppSidebar.tsx`
- Delete: `frontend/src/routes/_layout/items.tsx`, `frontend/src/routes/_layout/items_.$itemId.tsx`, `frontend/src/components/Items/`, `frontend/src/components/Pending/PendingItems.tsx`, `frontend/tests/items.spec.ts`
- Test: `frontend/tests/events.spec.ts`

**Interfaces:**
- Consumes: `EventsService.readEvents({ query: { skip, limit } }) -> { data: EventsPublic }`, `EventsService.readEvent({ path: { id } }) -> { data: EventDetail }`, `EventsService.createEvent({ body: EventCreate })`, `EventsService.updateEvent({ path: { id }, body: EventUpdate })`, `EventsService.deleteEvent({ path: { id } })`, `EventsService.readBookmarkedEvents({ query: { skip, limit } })`, `EventsService.setEventBookmark({ path: { id }, body: { is_bookmarked } })`. Operation ids follow the current hey-api `byTags` naming once the tag is `events`; use whatever names `generate-client.sh` emits, and do not wrap them.
- Produces: routes `/events` and `/events/$eventId`. Sidebar entry title `Events`, path `/events`.

- [ ] **Step 1: Write the failing Playwright test**

Rename `frontend/tests/items.spec.ts` to `frontend/tests/events.spec.ts` and point every `page.goto` and URL assertion at `/events` and `/events/{id}`. The create flow fills Name, Description, Venue ID, Performer ID, Time, and Price, then expects `Event created successfully`. Venue ID and Performer ID come from the `Opening Night` row on the events list (its `venue_id` and `performer_id`), not from new endpoints. A missing id still toasts `Event not found` and returns to `/events`. Seen, bookmark, edit, and delete cases stay, using `name` instead of `title`. Edit does not change venue or price.

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && bunx playwright test tests/events.spec.ts`

Expected: FAIL because `/events` is not a page and the client still calls `/api/v1/items/`.

- [ ] **Step 3: Regenerate the client and switch the UI**

From the repo root, run `bash scripts/generate-client.sh`. That script ends in `bun run lint`, which fails while pages still import `ItemsService`. Finish the UI switch in this same step, then run `cd frontend && bun run lint` again. Confirm `frontend/src/client/sdk.gen.ts` contains `/api/v1/events/` and does not contain `/api/v1/items/`. `frontend/src/client/index.ts` exports `EventsService`, `EventCreate`, `EventPublic`, and `EventDetail`, and does not export `ItemsService`.

List page `readEvents` into query key `["events"]`. Columns are ID, Name, Description, Creator, Read, bookmark. Empty description still reads `No description`. Row click goes to `/events/$eventId`. Copy ID and the actions menu do not navigate.

`AddEvent` submits `EventCreate`: required `name`, optional `description`, required `venue_id`, `performer_id`, `time`, and `price` `>= 0`. Success toast is `Event created successfully`.

`EditEvent` submits only `EventUpdate` fields: `name`, `description`, `time`, `performer_id`.

Detail page `readEvent` uses query key `["events", eventId]`, invalidates `["events"]` the way the item page invalidated `["items"]`, and shows name, description, time, venue id, performer id, creator, id, and the ticket list (row, seat, price, availability). 404 and 422 toast `Event not found` and navigate to `/events`. Bookmark and delete stay on the page; delete returns to `/events`.

Bookmarked page calls `readBookmarkedEvents`. Sidebar path is `/events`, label `Events`.

`BookmarkToggle` patches `["events"]`, `["events", id]`, and `["bookmarked"]` the same way it patched the item keys.

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd frontend && bunx playwright test tests/events.spec.ts`

Expected: PASS.

Also run: `cd frontend && bun run build`

Expected: TypeScript build succeeds with no reference to `ItemsService`, `ItemPublic`, or `ItemCreate`.

- [ ] **Step 5: Cleanup**

Delete `frontend/src/components/Items/`, `frontend/src/routes/_layout/items.tsx`, `frontend/src/routes/_layout/items_.$itemId.tsx`, `frontend/src/components/Pending/PendingItems.tsx`, and `frontend/tests/items.spec.ts` if any remain. Search `frontend/` for `/items`, `ItemsService`, `ItemPublic`, and `ItemCreate`. Search `backend/app` excluding `backend/app/alembic/versions` for a route prefix `/items`. Remove any leftover that is an item call or an unused item component. Leave old Alembic files that mention the `item` table.

- [ ] **Step 6: Commit**

Stage the generated client, the new events routes and components, the sidebar, the bookmarked page, the renamed Playwright spec, and the deletions. Commit message: `Point the frontend at events instead of items.`
