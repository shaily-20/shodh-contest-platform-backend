# SHODH Contest Platform

A small contest backend built with **FastAPI, PostgreSQL, Docker, and a Python code judge**. It is a working project prototype for the SHODH backend assessment, but it does **not** complete every requirement yet. See [What is complete](#what-is-complete-so-far) and [What is still missing](#what-is-still-missing).

## Run it locally

You need Docker Desktop (or Docker Engine) with Docker Compose. Open a terminal in the project folder—the one containing `docker-compose.yml`—and run:

```bash
docker compose up --build -d
```

Compose starts PostgreSQL, adds sample data, and starts the API and judge worker. The first run may take a few minutes while Docker downloads images.

Check that the services started:

```bash
docker compose ps -a
```

Open these links in your browser:

- **Web page:** <http://localhost:8000/>
- **API documentation:** <http://localhost:8000/docs>
- **Health check:** <http://localhost:8000/health>

The health check should show `"status":"healthy"` and `"database":"connected"`. If port 8000 is already being used, change the left side of `"8000:8000"` in `docker-compose.yml` to `8001`, restart Compose, and use `http://localhost:8001` instead.

To stop the services without deleting the database data:

```bash
docker compose down
```

**Do not use `docker compose down -v` if you want to keep the local database.**

## Try the sample project

The seed data creates two demo organizations, two contests, three problems, two organizer accounts, and two participant accounts. All sample accounts use this local-only password:

```text
sample-password-change-me
```

Sample usernames:

- Organizer: `seed-organizer-a` or `seed-organizer-b`
- Participant: `seed-participant-a` or `seed-participant-b`

### Sign in on the web page

1. Open <http://localhost:8000/>.
2. Enter `seed-participant-a` and the sample password above.
3. Choose a contest. The seeded participant is already joined to the first demo contest.
4. Choose a problem, enter Python code, and submit it.
5. Check the submission status and verdict on the page.

### Try the API in Swagger

1. Open <http://localhost:8000/docs>.
2. Expand **POST `/auth/token`**, click **Try it out**, and enter:

```json
{
  "external_id": "seed-participant-a",
  "password": "sample-password-change-me"
}
```

3. Click **Execute**. A successful response contains an `access_token`.
4. In endpoints that require sign-in, click **Authorize** and enter `Bearer ` followed by the token.
5. Use **GET `/contests`** to find the contest, and **GET `/organizations/{organization_id}/problems`** to find its problem IDs. The seeded participant is already joined to their demo contest.
6. Submit Python code using **POST `/contests/{contest_id}/submissions`**. Save the returned submission ID, then use **GET `/submissions/{submission_id}`** to check its status and verdict. Judging is asynchronous, so poll again if it is still queued or running.

A `201 Created` response from registration means the account was created. A `422` response means the request body did not match the required fields or validation rules; check the response's `detail` in Swagger. To use an existing account, sign in with `/auth/token` instead of registering it again.

## What is complete so far

This is a **partial implementation**, not full assessment completion. Current implemented features include:

- FastAPI endpoints for registration, sign-in, organizations, contests, participation, problems, and submissions.
- PostgreSQL storage and Docker Compose startup with demo seed data.
- Organizer/participant account roles and authentication checks on implemented endpoints.
- Problem versions and test-suite versions stored with submissions.
- Asynchronous submission judging with a Docker-based Python runner.
- Submission status lookup and an idempotency key for repeated submission requests.
- A basic browser interface for signing in, viewing contests, choosing a problem, submitting code, and checking status.

The `/docs` page is the most complete way to explore the API. The web page is a basic interface, not a finished production frontend.
