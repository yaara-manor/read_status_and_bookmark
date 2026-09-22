FROM python:3.14

ENV PYTHONUNBUFFERED=1

# Install uv
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#installing-uv
COPY --from=ghcr.io/astral-sh/uv:0.9.26 /uv /uvx /bin/

# Compile bytecode
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#compiling-bytecode
ENV UV_COMPILE_BYTECODE=1

# uv Cache
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#caching
ENV UV_LINK_MODE=copy

WORKDIR /app/

# Place executables in the environment at the front of the path
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#using-the-environment
ENV PATH="/app/.venv/bin:$PATH"

# Install dependencies
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#intermediate-layers
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=backend/pyproject.toml,target=backend/pyproject.toml \
    --mount=type=bind,source=packages/contracts,target=packages/contracts \
    --mount=type=bind,source=services/user-crud/pyproject.toml,target=services/user-crud/pyproject.toml \
    --mount=type=bind,source=services/event-crud/pyproject.toml,target=services/event-crud/pyproject.toml \
    --mount=type=bind,source=services/gateway/pyproject.toml,target=services/gateway/pyproject.toml \
    uv sync --frozen --no-install-workspace --package event-crud

COPY ./services/event-crud/scripts /app/services/event-crud/scripts

COPY ./services/event-crud/pyproject.toml ./services/event-crud/alembic.ini /app/services/event-crud/

COPY ./services/event-crud/app /app/services/event-crud/app

COPY ./packages/contracts /app/packages/contracts

# Sync the project
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#intermediate-layers
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=backend/pyproject.toml,target=backend/pyproject.toml \
    --mount=type=bind,source=services/user-crud/pyproject.toml,target=services/user-crud/pyproject.toml \
    --mount=type=bind,source=services/gateway/pyproject.toml,target=services/gateway/pyproject.toml \
    uv sync --frozen --package event-crud

WORKDIR /app/services/event-crud/

CMD ["fastapi", "run", "--workers", "4"]
