# Shodh Contest Platform Backend

FastAPI contest backend with JWT authentication and local Docker-based Python judging.

## Run locally

Requires Docker Engine/Desktop with Compose and a working local Docker daemon. Copy `.env.example` to `.env`, change both secrets, then run:

```bash
docker compose up --build
```

Open <http://localhost:8000/docs> for the interactive API, <http://localhost:8000/health> for API/database health, and <http://localhost:8000/redoc> for the reference docs. The first submission downloads the `python:3.12-alpine` judge image if it is not already present.

The local worker mounts `/var/run/docker.sock` to launch judge containers. **Access to this socket is effectively host-root access.** Keep this configuration on a trusted local machine; do not expose the worker or Docker socket to untrusted users/hosts. For a public service, use a dedicated isolated runner host or a hardened remote execution service.

## Authentication / bootstrap

Registration at `POST /auth/register` takes `external_id`, `display_name`, and a password of at least 12 characters. It returns a 12-hour bearer token. Use the `Authorize` button in `/docs` or send `Authorization: Bearer <access_token>`.

Participant registration does not need a key. To bootstrap an organizer, include `organizer_key` matching `ORGANIZER_REGISTRATION_KEY` from `.env`. Organizer accounts can create organizations, contests, and problem statements. Keep that key private. `POST /auth/token` accepts JSON credentials; `POST /auth/token/form` is the OAuth2 form endpoint.

## Basic workflow

1. Register an organizer using the bootstrap key.
2. Create an organization, then create a contest (`starts_at` and `ends_at` must be ISO 8601 timestamps with timezone).
3. Create a problem with test cases. Test input and expected output are private and are never returned by problem read endpoints.
4. Register a participant and call `POST /contests/{contest_id}/join` using its bearer token.
5. Submit Python (`language: "python"`) code to `POST /contests/{contest_id}/submissions`; poll `GET /submissions/{submission_id}`. Identity is taken from the token, not request data.

The judging worker claims queued attempts from PostgreSQL, runs each case in a fresh container, and records the verdict. It supports Python 3 only. Containers have networking disabled, a read-only root filesystem, a non-root user, dropped Linux capabilities, no-new-privileges, and CPU, memory, process, timeout, and output limits. These controls are defense in depth, not a guarantee of safe execution on a shared/public host.

## Existing local database

The account table is additive and is created when the API starts. Existing identities do not have login credentials; create a new account with a new `external_id`. Back up data before resetting anything. `docker compose down -v` deletes the local database and is not required for upgrades.

## Limitations

This is a local-development baseline, not a production-ready auth or judge service: no email verification/password reset/rate limiting, and execution isolation depends on your host's Docker/kernel configuration. Configure real secrets, TLS, backups, migrations, monitoring, and an isolated runner before deployment.
