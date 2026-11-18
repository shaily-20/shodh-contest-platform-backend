# Shodh Contest Platform Backend

FastAPI service entry point: `main:app` (also available as `app.main:app`).

## Run locally

Requires Python 3.12+ and PostgreSQL. Set `DATABASE_URL`, then:

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

OpenAPI docs are at `/docs`; `/health` checks the database connection. Docker Compose is the intended local stack:

```bash
docker compose up --build
```

The repository is under active development; this starter currently provides the ASGI application and relational schema initialization. It is not yet a complete submission/judging system, and the runner currently does not execute untrusted programs.
