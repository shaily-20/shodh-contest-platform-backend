# Shodh Contest Platform Backend

FastAPI contest backend with PostgreSQL and Docker-isolated Python judging.

## Start from scratch

Requires Docker Engine/Desktop and Compose. From the repository root:

```bash
cp .env.example .env
# Replace JWT_SECRET and ORGANIZER_REGISTRATION_KEY with separate random values.
docker compose up --build
```

Compose starts PostgreSQL, runs the idempotent demo seed, then starts the API and worker. Open <http://localhost:8000/docs> and check <http://localhost:8000/health>. `docker compose down` stops services; `docker compose down -v` also deletes database data.

### Seed accounts

The local seed creates two organizations, two organizer identities, two participants, two contests, and three small problems. All four accounts use the temporary password `sample-password-change-me`. Log in with `POST /auth/token`, using one of these `external_id` values:

- `seed-organizer-a`
- `seed-organizer-b`
- `seed-participant-a`
- `seed-participant-b`

Change or remove these sample accounts before any non-local deployment. Seed data is intended only for evaluation. Re-run seeding with `docker compose run --rm seed`; it will leave existing seed data untouched.

## Authentication and API workflow

Registration at `POST /auth/register` accepts `external_id`, `display_name`, and a password of at least 12 characters. Provide the configured `ORGANIZER_REGISTRATION_KEY` to create an organizer. `POST /auth/token` accepts JSON credentials and returns a bearer token. Use **Authorize** in `/docs`.

The supported workflow is to create an organization and contest as an organizer, create a problem with test cases, join a contest as a participant, submit Python code to `POST /contests/{contest_id}/submissions`, and poll `GET /submissions/{submission_id}`. Contest timestamps must include a timezone. Submission requires an active contest and prior participation. Submission keys are unique per participant and contest; reusing the key with a different code or problem returns a conflict.

## Judging and security limits

The PostgreSQL record is the queue: the API stores the submission and a queued attempt in one database transaction, and workers claim queued or expired leased work. The worker runs Python 3 only. Each test case runs in a fresh Docker container with network disabled, a read-only root filesystem, a non-root user, dropped capabilities, no-new-privileges, and configured CPU, memory, process and time limits. Container cleanup is attempted after execution.

**Important:** the trusted worker mounts `/var/run/docker.sock`; access to this socket is effectively host-root access. Submitted code does not receive that mount, but this design is suitable only for trusted local development/evaluation—not a public multi-tenant production service. Use a separately isolated runner host/service before public deployment. Vercel functions do not provide the Docker daemon required by this worker.

## Assignment status and known limitations

This repository is an evaluation prototype, not a claim of full take-home compliance. In particular, do not report the following as complete unless separately implemented and verified: leaderboard scoring/penalties and deterministic tie-breaks; organizer rejudge API; bounded retry/dead-letter behavior and stale-worker fencing; migrations; complete organization-scoped authorization; hidden-test confidentiality audit; real-runner and barrier-coordinated multi-process race tests; repeatable load results and query-plan comparison; structured cross-service tracing. Run and document these checks before claiming the corresponding requirement is satisfied.

The included seed is deterministic in names and content but uses generated database IDs and a time-relative contest window. `Base.metadata.create_all` is still used at API startup; Alembic migrations should replace it for a durable production schema. Do not publish real credentials, hidden tests, or candidate code in logs.

## Verification

```bash
docker compose ps
curl http://localhost:8000/health
docker compose logs --tail=100 api worker seed
```

OpenAPI documentation is available at `/docs`; the OpenAPI JSON is `/openapi.json`. The Docker runner should be exercised locally with accepted, wrong-answer, runtime-error, timeout and excessive-output submissions before submitting the take-home. Record the commit, machine resources, dataset, concurrency, execution mode, latency percentiles, errors, and queue delay for any workload report—do not invent performance results.
