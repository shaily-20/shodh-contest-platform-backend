# Shodh Contest Platform Backend

FastAPI backend for managing organizations, participants, contests, problems, and code submissions. The interactive REST interface is generated from the API schemas.

## Run the complete local stack

Requires Docker Desktop / Docker Engine with the Compose plugin:

```bash
docker compose up --build
```

Once the containers are healthy:

- API landing response: <http://localhost:8000/>
- Interactive Swagger UI: <http://localhost:8000/docs>
- ReDoc: <http://localhost:8000/redoc>
- Database health check: <http://localhost:8000/health>

Stop with `docker compose down`; add `-v` only if you also want to delete the local database volume.

## Run the API without Docker

Requires Python 3.12+ and a running PostgreSQL database. Set `DATABASE_URL` to an async PostgreSQL URL, then run:

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## API quick start

Use `/docs` to explore and invoke every endpoint. Typical setup sequence:

1. `POST /organizations` — create an organization.
2. `POST /identities` — create a participant identity.
3. `POST /contests` — create a contest for the organization.
4. `POST /organizations/{organization_id}/problems` — add a problem statement and private test cases.
5. `POST /contests/{contest_id}/join` — register the participant.
6. `POST /contests/{contest_id}/submissions` — create a submission; include a unique `idempotency_key`.
7. `GET /submissions/{submission_id}?identity_id=...` — check submission status.

Submission records and judging attempts are persisted in PostgreSQL. **This repository does not yet include a code-execution/judging worker**, so submissions remain `queued`; do not treat them as evaluated. User identity is currently supplied as an ID in requests rather than verified authentication, so this is a development starter, not a production-ready public service.

## Configuration

`DATABASE_URL` is configurable through the environment (default is the Compose PostgreSQL service). Schema creation at API startup is intended for local development; production deployments should use versioned Alembic migrations. The API does not expose private test inputs/expected outputs through its problem read endpoints.
