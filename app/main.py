from contextlib import asynccontextmanager
from datetime import datetime, timezone
import hashlib
import json

from fastapi import FastAPI, Header, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db import SessionLocal, engine
from app.models import (
    AttemptStatus,
    Base,
    Contest,
    Identity,
    JudgingAttempt,
    Membership,
    Organization,
    OrgRole,
    Participation,
    Problem,
    ProblemVersion,
    Submission,
    TestCase,
    TestSuite,
)
from app.schemas import (
    ContestCreate,
    ContestOut,
    IdentityCreate,
    IdentityOut,
    JoinContest,
    OrganizationCreate,
    OrganizationOut,
    ProblemCreate,
    ProblemOut,
    SubmissionCreate,
    SubmissionOut,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Convenient for local development. Use Alembic migrations for production deployments.
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(
    title="Shodh Contest Platform API",
    version="1.0.0",
    description=(
        "REST API for organizations, contests, participants, problems, and submissions. "
        "Interactive API documentation is available at /docs."
    ),
    lifespan=lifespan,
)


@app.get("/", tags=["health"])
async def root() -> dict[str, str]:
    return {
        "service": "shodh-contest-platform-backend",
        "status": "ok",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    from sqlalchemy import text

    async with SessionLocal() as session:
        await session.execute(text("SELECT 1"))
    return {"status": "healthy", "database": "connected"}


@app.post("/organizations", response_model=OrganizationOut, status_code=status.HTTP_201_CREATED, tags=["organizations"])
async def create_organization(payload: OrganizationCreate):
    async with SessionLocal() as session:
        organization = Organization(name=payload.name)
        session.add(organization)
        try:
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            raise HTTPException(status_code=409, detail="An organization with that name already exists") from exc
        await session.refresh(organization)
        return organization


@app.get("/organizations", response_model=list[OrganizationOut], tags=["organizations"])
async def list_organizations(limit: int = Query(default=100, ge=1, le=500), offset: int = Query(default=0, ge=0)):
    async with SessionLocal() as session:
        result = await session.scalars(select(Organization).order_by(Organization.id).offset(offset).limit(limit))
        return list(result)


@app.post("/identities", response_model=IdentityOut, status_code=status.HTTP_201_CREATED, tags=["participants"])
async def create_identity(payload: IdentityCreate):
    async with SessionLocal() as session:
        identity = Identity(**payload.model_dump())
        session.add(identity)
        try:
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            raise HTTPException(status_code=409, detail="An identity with that external_id already exists") from exc
        await session.refresh(identity)
        return identity


@app.post("/contests", response_model=ContestOut, status_code=status.HTTP_201_CREATED, tags=["contests"])
async def create_contest(payload: ContestCreate):
    async with SessionLocal() as session:
        if await session.get(Organization, payload.organization_id) is None:
            raise HTTPException(status_code=404, detail="Organization not found")
        contest = Contest(**payload.model_dump())
        session.add(contest)
        await session.commit()
        await session.refresh(contest)
        return contest


@app.get("/contests", response_model=list[ContestOut], tags=["contests"])
async def list_contests(
    organization_id: int | None = Query(default=None, gt=0),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    query = select(Contest).order_by(Contest.starts_at.desc()).offset(offset).limit(limit)
    if organization_id is not None:
        query = query.where(Contest.organization_id == organization_id)
    async with SessionLocal() as session:
        return list(await session.scalars(query))


@app.post("/contests/{contest_id}/join", status_code=status.HTTP_200_OK, tags=["contests"])
async def join_contest(contest_id: int, payload: JoinContest):
    async with SessionLocal() as session:
        contest = await session.get(Contest, contest_id)
        identity = await session.get(Identity, payload.identity_id)
        if contest is None:
            raise HTTPException(status_code=404, detail="Contest not found")
        if identity is None:
            raise HTTPException(status_code=404, detail="Identity not found")
        membership = await session.get(Membership, (contest.organization_id, identity.id))
        if membership is None:
            session.add(Membership(organization_id=contest.organization_id, identity_id=identity.id, role=OrgRole.MEMBER))
        participation = await session.get(Participation, (contest_id, identity.id))
        if participation is None:
            session.add(Participation(contest_id=contest_id, identity_id=identity.id))
            await session.commit()
        return {"contest_id": contest_id, "identity_id": identity.id, "joined": True}


@app.post(
    "/organizations/{organization_id}/problems",
    response_model=ProblemOut,
    status_code=status.HTTP_201_CREATED,
    tags=["problems"],
)
async def create_problem(organization_id: int, payload: ProblemCreate):
    async with SessionLocal() as session:
        if await session.get(Organization, organization_id) is None:
            raise HTTPException(status_code=404, detail="Organization not found")
        existing = await session.scalar(
            select(Problem).where(Problem.organization_id == organization_id, Problem.slug == payload.slug)
        )
        if existing:
            raise HTTPException(status_code=409, detail="A problem with that slug already exists in this organization")
        problem = Problem(organization_id=organization_id, slug=payload.slug, title=payload.title)
        session.add(problem)
        await session.flush()
        version = ProblemVersion(problem_id=problem.id, version=1, statement=payload.statement)
        session.add(version)
        await session.flush()
        suite = TestSuite(problem_version_id=version.id, version=1)
        session.add(suite)
        await session.flush()
        session.add_all(
            TestCase(suite_id=suite.id, input=case.input, expected_output=case.expected_output, ordinal=index)
            for index, case in enumerate(payload.test_cases, start=1)
        )
        await session.commit()
        return ProblemOut(
            id=problem.id,
            organization_id=problem.organization_id,
            slug=problem.slug,
            title=problem.title,
            version=version.version,
            statement=version.statement,
        )


@app.get("/organizations/{organization_id}/problems", response_model=list[ProblemOut], tags=["problems"])
async def list_problems(organization_id: int):
    async with SessionLocal() as session:
        rows = (await session.execute(
            select(Problem, ProblemVersion)
            .join(ProblemVersion, ProblemVersion.problem_id == Problem.id)
            .where(Problem.organization_id == organization_id)
            .order_by(Problem.id, ProblemVersion.version.desc())
        )).all()
        latest = {}
        for problem, version in rows:
            latest.setdefault(problem.id, ProblemOut(
                id=problem.id,
                organization_id=problem.organization_id,
                slug=problem.slug,
                title=problem.title,
                version=version.version,
                statement=version.statement,
            ))
        return list(latest.values())


@app.get("/problems/{problem_id}", response_model=ProblemOut, tags=["problems"])
async def get_problem(problem_id: int):
    async with SessionLocal() as session:
        problem = await session.get(Problem, problem_id)
        if problem is None:
            raise HTTPException(status_code=404, detail="Problem not found")
        version = await session.scalar(
            select(ProblemVersion).where(ProblemVersion.problem_id == problem_id).order_by(ProblemVersion.version.desc()).limit(1)
        )
        if version is None:
            raise HTTPException(status_code=404, detail="Problem statement not found")
        return ProblemOut(
            id=problem.id,
            organization_id=problem.organization_id,
            slug=problem.slug,
            title=problem.title,
            version=version.version,
            statement=version.statement,
        )


@app.post(
    "/contests/{contest_id}/submissions",
    response_model=SubmissionOut,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["submissions"],
)
async def create_submission(contest_id: int, payload: SubmissionCreate):
    async with SessionLocal() as session:
        contest = await session.get(Contest, contest_id)
        if contest is None:
            raise HTTPException(status_code=404, detail="Contest not found")
        now = datetime.now(timezone.utc)
        if now < contest.starts_at or now > contest.ends_at:
            raise HTTPException(status_code=409, detail="Contest is not currently accepting submissions")
        if await session.get(Participation, (contest_id, payload.identity_id)) is None:
            raise HTTPException(status_code=403, detail="Join the contest before submitting")
        problem = await session.get(Problem, payload.problem_id)
        if problem is None or problem.organization_id != contest.organization_id:
            raise HTTPException(status_code=404, detail="Problem not found in this contest organization")
        version = await session.scalar(
            select(ProblemVersion).where(ProblemVersion.problem_id == problem.id).order_by(ProblemVersion.version.desc()).limit(1)
        )
        suite = await session.scalar(
            select(TestSuite).where(TestSuite.problem_version_id == version.id).order_by(TestSuite.version.desc()).limit(1)
        ) if version else None
        if version is None or suite is None:
            raise HTTPException(status_code=409, detail="Problem does not have an active test suite")
        request_hash = hashlib.sha256(json.dumps({
            "problem_id": problem.id,
            "language": payload.language,
            "code": payload.code,
        }, sort_keys=True).encode()).hexdigest()
        existing = await session.scalar(select(Submission).where(
            Submission.contest_id == contest_id,
            Submission.identity_id == payload.identity_id,
            Submission.idempotency_key == payload.idempotency_key,
        ))
        if existing is not None:
            if existing.request_hash != request_hash:
                raise HTTPException(status_code=409, detail="Idempotency key was already used for a different submission")
            attempt = await session.scalar(select(JudgingAttempt).where(
                JudgingAttempt.submission_id == existing.id,
                JudgingAttempt.attempt_number == 1,
            ))
            return SubmissionOut(
                id=existing.id, contest_id=existing.contest_id, identity_id=existing.identity_id,
                problem_id=existing.problem_id, language=existing.language,
                status=attempt.status.value if attempt else "queued",
                verdict=attempt.verdict.value if attempt and attempt.verdict else None,
                created_at=existing.created_at,
            )
        submission = Submission(
            contest_id=contest_id,
            identity_id=payload.identity_id,
            problem_id=problem.id,
            problem_version_id=version.id,
            suite_id=suite.id,
            language=payload.language,
            code=payload.code,
            runtime_config={},
            idempotency_key=payload.idempotency_key,
            request_hash=request_hash,
        )
        session.add(submission)
        await session.flush()
        attempt = JudgingAttempt(
            submission_id=submission.id,
            attempt_number=1,
            status=AttemptStatus.QUEUE,
            problem_version_id=version.id,
            suite_id=suite.id,
            language=payload.language,
            code=payload.code,
            runtime_config={},
        )
        session.add(attempt)
        await session.commit()
        await session.refresh(submission)
        return SubmissionOut(
            id=submission.id, contest_id=contest_id, identity_id=payload.identity_id,
            problem_id=problem.id, language=payload.language, status=attempt.status.value,
            verdict=None, created_at=submission.created_at,
        )


@app.get("/submissions/{submission_id}", response_model=SubmissionOut, tags=["submissions"])
async def get_submission(submission_id: int, identity_id: int = Query(gt=0)):
    async with SessionLocal() as session:
        submission = await session.get(Submission, submission_id)
        if submission is None or submission.identity_id != identity_id:
            raise HTTPException(status_code=404, detail="Submission not found")
        attempt = await session.scalar(
            select(JudgingAttempt).where(JudgingAttempt.submission_id == submission_id)
            .order_by(JudgingAttempt.attempt_number.desc()).limit(1)
        )
        return SubmissionOut(
            id=submission.id, contest_id=submission.contest_id, identity_id=submission.identity_id,
            problem_id=submission.problem_id, language=submission.language,
            status=attempt.status.value if attempt else "queued",
            verdict=attempt.verdict.value if attempt and attempt.verdict else None,
            created_at=submission.created_at,
        )
