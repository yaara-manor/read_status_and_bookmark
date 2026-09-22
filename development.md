# FastAPI Project - Development

## Local Development

For local development, run PostgreSQL, Redis, and Mailpit with Docker Compose, and run the gateway, both domain services, and the Vite development server locally.

Start the supporting services:

```bash
docker compose up -d db redis mailpit
```

From `services/user-crud`, prepare the user database. This migrates and creates the first superuser:

```bash
uv run bash scripts/prestart.sh
```

From `services/event-crud`, prepare the event database:

```bash
uv run bash scripts/prestart.sh
```

Start the three FastAPI development servers. The domain services listen on other ports so the gateway can use `8000`.

```bash
# services/user-crud
uv run fastapi dev --port 8001

# services/event-crud
uv run fastapi dev --port 8002

# services/gateway
USER_CRUD_URL=http://127.0.0.1:8001 EVENT_CRUD_URL=http://127.0.0.1:8002 uv run fastapi dev --port 8000
```

In another terminal, from the project root, install the frontend dependencies and start the Vite development server:

```bash
bun install
bun run dev
```

`VITE_API_URL` is the gateway at `http://localhost:8000`.

Now you can open these URLs:

Frontend development server: <http://localhost:5173>

Gateway API: <http://localhost:8000>

Automatic interactive API documentation with Swagger UI: <http://localhost:8000/docs>

Mailpit: <http://localhost:8025>

### Frontend Served by the Gateway

The gateway image builds the frontend and copies it to `app/frontend`. Compose serves that build from the gateway at <http://localhost:8000>.

## Full Stack with Docker Compose

To run the gateway, both domain services, and the built frontend in Docker Compose:

```bash
docker compose run --rm user-crud bash scripts/prestart.sh
docker compose run --rm event-crud bash scripts/prestart.sh
docker compose up -d
```

Now you can open these URLs:

Application, with the frontend and API served by the gateway: <http://localhost:8000>

Automatic interactive API documentation with Swagger UI: <http://localhost:8000/docs>

Adminer, database web administration: <http://localhost:8080>

Traefik UI, to see how the routes are being handled by the proxy: <http://localhost:8090>

Mailpit: <http://localhost:8025>

Stop a locally running gateway before starting the Compose gateway because both use port `8000`.

**Note**: The first time you start the stack, it might take a minute for all the services to be ready. To monitor it, use `docker compose logs`, or `docker compose logs gateway` for the gateway service.

## Mailpit

[Mailpit](https://mailpit.axllent.org) captures emails sent during local development instead of delivering them. The local user service connects to it at `localhost:1025`, and the Compose user service connects to the `mailpit` service. Captured emails are available at <http://localhost:8025>.

## Docker Compose Files and Environment Variables

The main `compose.yml` file contains the configuration shared by the whole stack. Docker Compose loads it automatically.

The `compose.override.yml` file adds local development settings, such as published ports. Docker Compose also loads it automatically and applies it on top of `compose.yml`.

The `compose.deploy.yml` file contains the deployment-specific settings, including HTTPS and automatic certificate handling. It is explicitly combined with `compose.yml` when deploying the application.

The services read local settings from the `.env` file. Docker Compose also uses it for variable interpolation and passes the settings each container needs.

After changing variables, make sure you restart the stack:

```bash
docker compose up -d
```

## The `.env` File

The tracked `.env` file contains local development defaults, passwords, and other configuration. Its hostnames use `localhost` for processes running on your machine. Docker Compose overrides hostnames such as the database, Redis, and SMTP server with their Compose service names.

Do not store deployment secrets in `.env`. Configure them as described in the [FastAPI Cloud deployment guide](./deployment.md) or the [Docker Compose deployment guide](./deployment-docker-compose.md).

## Pre-commit Hooks and Code Linting

The project uses [prek](https://prek.j178.dev/), a modern alternative to [pre-commit](https://pre-commit.com/), for code linting and formatting.

You can find a file `.pre-commit-config.yaml` with configurations at the root of the project.

### Install `prek` to Run Automatically

`prek` is already part of the dependencies of the project.

From the project root, install the Git hook so that `prek` runs automatically before each commit:

```bash
uv run prek install -f
```

The `-f` flag forces the installation, in case there was already a `pre-commit` hook previously installed.

Now whenever you try to commit, for example with:

```bash
git commit
```

`prek` will check and format the code you are about to commit. If it modifies any files, add those files to Git again before committing.

### Run `prek` Manually

You can also run `prek` manually on all files from the project root:

```bash
uv run prek run --all-files
```
