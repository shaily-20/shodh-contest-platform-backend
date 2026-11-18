from contextlib import asynccontextmanager
from datetime import datetime, timezone
import hashlib
import json

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.auth import (
    create_access_token,
    current_account,
    hash_password,
    organizer_account,
    verify_password,
)
from app.config import settings
from app.db import SessionLocal, engine
from app.models import (
    Account,
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
    IdentityOut,
    LoginRequest,
    OrganizationCreate,
    OrganizationOut,
    ProblemCreate,
    ProblemOut,
    RegisterRequest,
    SubmissionCreate,
    SubmissionOut,
    TokenOut,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(
    title="Shodh Contest Platform API",
    version="1.1.0",
    description="Authenticated contest API with Docker-isolated Python submissions. See /docs.",
    lifespan=lifespan,
)


def submission_response(submission: Submission, attempt: JudgingAttempt | None) -> SubmissionOut:
    return SubmissionOut(
        id=submission.id,
        contest_id=submission.contest_id,
        identity_id=submission.identity_id,
        problem_id=submission.problem_id,
        language=submission.language,
        status=attempt.status.value if attempt else "queued",
        verdict=attempt.verdict.value if attempt and attempt.verdict else None,
        created_at=submission.created_at,
    )


@app.get("/", tags=["health"])
async def root():
    return {"service": "shodh-contest-platform-backend", "status": "ok", "docs": "/docs", "health": "/health"}


@app.get("/health", tags=["health"])
async def health():
    async with SessionLocal() as session:
        await session.execute(text("SELECT 1"))
    return {"status": "healthy", "database": "connected"}


@app.post("/auth/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED, tags=["authentication"])
async def register(payload: RegisterRequest):
    role = "participant"
    if payload.organizer_key:
        if not settings.organizer_registration_key or not __import__("hmac").compare_digest(
            payload.organizer_key, settings.organizer_registration_key
        ):
            raise HTTPException(status_code=403, detail="Invalid organizer registration key")
        role = "organizer"
    async with SessionLocal() as session:
        identity = Identity(external_id=payload.external_id, display_name=payload.display_name)
        session.add(identity)
        try:
            await session.flush()
            session.add(Account(identity_id=identity.id, password_hash=hash_password(payload.password), role=role))
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            raise HTTPException(status_code=409, detail="That external_id is already registered") from exc
        return TokenOut(
            access_token=create_access_token(identity.id, role),
            identity_id=identity.id,
            display_name=identity.display_name,
            role=role,
        )


@app.post("/auth/token", response_model=TokenOut, tags=["authentication"])
async def login_json(payload: LoginRequest):
    async with SessionLocal() as session:
        identity = await session.scalar(select(Identity).where(Identity.external_id == payload.external_id))
        account = await session.get(Account, identity.id) if identity else None
        if identity is None or account is None or not verify_password(payload.password, account.password_hash):
            raise HTTPException(status_code=401, detail="Incorrect username or password", headers={"WWW-Authenticate": "Bearer"})
        return TokenOut(
            access_token=create_access_token(identity.id, account.role),
            identity_id=identity.id,
            display_name=identity.display_name,
            role=account.role,
        )


@app.post("/auth/token/form", response_model=TokenOut, include_in_schema=False)
async def login_form(form: OAuth2PasswordRequestForm = Depends()):
    return await login_json(LoginRequest(external_id=form.username, password=form.password))


@app.get("/auth/me", response_model=IdentityOut, tags=["authentication"])
async def me(account_pair=Depends(current_account)):
    return account_pair[0]


@app.post("/organizations", response_model=OrganizationOut, status_code=status.HTTP_201_CREATED, tags=["organizations"])
async def create_organization(payload: OrganizationCreate, _=Depends(organizer_account)):
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
        return list(await session.scalars(select(Organization).order_by(Organization.id).offset(offset).limit(limit)))


@app.get("/identities", response_model=list[IdentityOut], tags=["participants"])
async def list_identities(
    limit: int = Query(default=100, ge=1, le=500), offset: int = Query(default=0, ge=0),
    _=Depends(organizer_account),
):
    async with SessionLocal() as session:
        return list(await session.scalars(select(Identity).order_by(Identity.id).offset(offset).limit(limit)))


@app.post("/contests", response_model=ContestOut, status_code=status.HTTP_201_CREATED, tags=["contests"])
async def create_contest(payload: ContestCreate, _=Depends(organizer_account)):
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
    limit: int = Query(default=100, ge=1, le=500), offset: int = Query(default=0, ge=0),
):
    query = select(Contest).order_by(Contest.starts_at.desc()).offset(offset).limit(limit)
    if organization_id is not None:
        query = query.where(Contest.organization_id == organization_id)
    async with SessionLocal() as session:
        return list(await session.scalars(query))


@app.post("/contests/{contest_id}/join", tags=["contests"])
async def join_contest(contest_id: int, account_pair=Depends(current_account)):
    identity = account_pair[0]
    async with SessionLocal() as session:
        contest = await session.get(Contest, contest_id)
        if contest is None:
            raise HTTPException(status_code=404, detail="Contest not found")
        membership = await session.get(Membership, (contest.organization_id, identity.id))
        if membership is None:
            session.add(Membership(organization_id=contest.organization_id, identity_id=identity.id, role=OrgRole.MEMBER))
        participation = await session.get(Participation, (contest_id, identity.id))
        if participation is None:
            session.add(Participation(contest_id=contest_id, identity_id=identity.id))
            await session.commit()
        return {"contest_id": contest_id, "identity_id": identity.id, "joined": True}


@app.post("/organizations/{organization_id}/problems", response_model=ProblemOut, status_code=201, tags=["problems"])
async def create_problem(organization_id: int, payload: ProblemCreate, _=Depends(organizer_account)):
    async with SessionLocal() as session:
        if await session.get(Organization, organization_id) is None:
            raise HTTPException(status_code=404, detail="Organization not found")
        if await session.scalar(select(Problem).where(Problem.organization_id == organization_id, Problem.slug == payload.slug)):
            raise HTTPException(status_code=409, detail="Problem slug already exists")
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
        return ProblemOut(id=problem.id, organization_id=organization_id, slug=problem.slug, title=problem.title,
                          version=version.version, statement=version.statement)


@app.get("/organizations/{organization_id}/problems", response_model=list[ProblemOut], tags=["problems"])
async def list_problems(organization_id: int):
    async with SessionLocal() as session:
        rows = (await session.execute(
            select(Problem, ProblemVersion).join(ProblemVersion, ProblemVersion.problem_id == Problem.id)
            .where(Problem.organization_id == organization_id).order_by(Problem.id, ProblemVersion.version.desc())
        )).all()
        latest = {}
        for problem, version in rows:
            latest.setdefault(problem.id, ProblemOut(id=problem.id, organization_id=problem.organization_id,
                slug=problem.slug, title=problem.title, version=version.version, statement=version.statement))
        return list(latest.values())


@app.post("/contests/{contest_id}/submissions", response_model=SubmissionOut, status_code=202, tags=["submissions"])
async def create_submission(contest_id: int, payload: SubmissionCreate, account_pair=Depends(current_account)):
    identity = account_pair[0]
    async with SessionLocal() as session:
        contest = await session.get(Contest, contest_id)
        if contest is None:
            raise HTTPException(status_code=404, detail="Contest not found")
        now = datetime.now(timezone.utc)
        starts = contest.starts_at if contest.starts_at.tzinfo else contest.starts_at.replace(tzinfo=timezone.utc)
        ends = contest.ends_at if contest.ends_at.tzinfo else contest.ends_at.replace(tzinfo=timezone.utc)
        if now < starts or now > ends:
            raise HTTPException(status_code=409, detail="Contest is not currently accepting submissions")
        if await session.get(Participation, (contest_id, identity.id)) is None:
            raise HTTPException(status_code=403, detail="Join the contest before submitting")
        problem = await session.get(Problem, payload.problem_id)
        if problem is None or problem.organization_id != contest.organization_id:
            raise HTTPException(status_code=404, detail="Problem not found in this contest organization")
        version = await session.scalar(select(ProblemVersion).where(ProblemVersion.problem_id == problem.id)
                                       .order_by(ProblemVersion.version.desc()).limit(1))
        suite = await session.scalar(select(TestSuite).where(TestSuite.problem_version_id == version.id)
                                     .order_by(TestSuite.version.desc()).limit(1)) if version else None
        if version is None or suite is None:
            raise HTTPException(status_code=409, detail="Problem has no active test suite")
        digest = hashlib.sha256(json.dumps({"problem_id": problem.id, "language": payload.language, "code": payload.code}, sort_keys=True).encode()).hexdigest()
        existing = await session.scalar(select(Submission).where(
            Submission.contest_id == contest_id, Submission.identity_id == identity.id,
            Submission.idempotency_key == payload.idempotency_key))
        if existing:
            if existing.request_hash != digest:
                raise HTTPException(status_code=409, detail="Idempotency key already used for a different submission")
            attempt = await session.scalar(select(JudgingAttempt).where(JudgingAttempt.submission_id == existing.id)
                                           .order_by(JudgingAttempt.attempt_number.desc()).limit(1))
            return submission_response(existing, attempt)
        submission = Submission(contest_id=contest_id, identity_id=identity.id, problem_id=problem.id,
            problem_version_id=version.id, suite_id=suite.id, language=payload.language, code=payload.code,
            runtime_config={}, idempotency_key=payload.idempotency_key, request_hash=digest)
        session.add(submission)
        await session.flush()
        attempt = JudgingAttempt(submission_id=submission.id, attempt_number=1, status=AttemptStatus.QUEUE,
            problem_version_id=version.id, suite_id=suite.id, language=payload.language, code=payload.code,
            runtime_config={})
        session.add(attempt)
        await session.commit()
        await session.refresh(submission)
        return submission_response(submission, attempt)


@app.get("/submissions/{submission_id}", response_model=SubmissionOut, tags=["submissions"])
async def get_submission(submission_id: int, account_pair=Depends(current_account)):
    async with SessionLocal() as session:
        submission = await session.get(Submission, submission_id)
        if submission is None or submission.identity_id != account_pair[0].id:
            raise HTTPException(status_code=404, detail="Submission not found")
        attempt = await session.scalar(select(JudgingAttempt).where(JudgingAttempt.submission_id == submission_id)
                                       .order_by(JudgingAttempt.attempt_number.desc()).limit(1))
        return submission_response(submission, attempt)
