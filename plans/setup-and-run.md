# Setup and run (local FastAPI + Vite)

## Goal
PostgreSQL + Mailpit via Compose. FastAPI via `uv`. Frontend via `bun`.

## Steps
1. `fix_database_url` — `.env` `DATABASE_URL` must use `POSTGRES_PASSWORD`, not `$ym`.
2. `start_db_mailpit` — `docker compose up -d db mailpit`
3. `backend_sync` — `uv sync` in `backend/`
4. `backend_prestart` — `uv run bash scripts/prestart.sh` (`alembic upgrade head`, `python app/initial_data.py`)
5. `backend_dev` — `uv run fastapi dev`
6. `frontend_install` — `bun install` at repo root
7. `frontend_dev` — `bun run dev`

## URLs
- Frontend: http://localhost:5173
- API: http://localhost:8000
- Docs: http://localhost:8000/docs
- Mailpit: http://localhost:8025

## Login (defaults in `.env`)
- `FIRST_SUPERUSER` / `FIRST_SUPERUSER_PASSWORD`
