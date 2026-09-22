#! /usr/bin/env bash

set -e
set -x

cd services/gateway
FASTAPI_ENV=development \
PROJECT_NAME="${PROJECT_NAME:-Ticketmaster}" \
USER_CRUD_URL="${USER_CRUD_URL:-http://user.test}" \
EVENT_CRUD_URL="${EVENT_CRUD_URL:-http://event.test}" \
INTERNAL_API_KEY="${INTERNAL_API_KEY:-test-internal-key}" \
uv run python -c "import app.main; import json; print(json.dumps(app.main.app.openapi()))" > ../../frontend/openapi.json
cd ../..
bun run --filter frontend generate-client
