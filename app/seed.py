"""Create the schema and deterministic sample data for local evaluation.

Run with ``python -m app.seed`` after PostgreSQL is available. Seed identities
use the sample passwords documented in README.md; never use these credentials
outside a local evaluation environment.
"""
import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.auth import hash_password
from app.db import SessionLocal, engine
from app.models import (
    Account,
    Base,
    Contest,
    Identity,
    Membership,
    Organization,
    OrgRole,
    Problem,
    ProblemVersion,
    TestCase,
    TestSuite,
)

SAMPLE_PASSWORD = "sample-password-change-me"


async def seed() -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with SessionLocal() as session:
        existing = await session.scalar(select(Identity).where(Identity.external_id == "seed-organizer-a"))
        if existing:
            return

        orgs = [Organization(name="Shodh Demo A"), Organization(name="Shodh Demo B")]
        session.add_all(orgs)
        await session.flush()

        identities = [
            Identity(external_id="seed-organizer-a", display_name="Demo Organizer A"),
            Identity(external_id="seed-organizer-b", display_name="Demo Organizer B"),
            Identity(external_id="seed-participant-a", display_name="Demo Participant A"),
            Identity(external_id="seed-participant-b", display_name="Demo Participant B"),
        ]
        session.add_all(identities)
        await session.flush()
        for identity, role in zip(identities, ["organizer", "organizer", "participant", "participant"]):
            session.add(Account(identity_id=identity.id, password_hash=hash_password(SAMPLE_PASSWORD), role=role))
        for org, organizer in zip(orgs, identities[:2]):
            session.add(Membership(organization_id=org.id, identity_id=organizer.id, role=OrgRole.ORGANIZER))

        now = datetime.now(timezone.utc)
        contests = [
            Contest(organization_id=orgs[0].id, title="Demo Contest A", starts_at=now - timedelta(days=1), ends_at=now + timedelta(days=30)),
            Contest(organization_id=orgs[1].id, title="Demo Contest B", starts_at=now - timedelta(days=1), ends_at=now + timedelta(days=30)),
        ]
        session.add_all(contests)
        await session.flush()
        for contest, participant in zip(contests, [identities[2], identities[3]]):
            from app.models import Participation
            session.add(Participation(contest_id=contest.id, identity_id=participant.id))

        problems = [
            (orgs[0], "sum-two", "Sum Two", "Read two integers and print their sum.", [("2 3\n", "5\n")]),
            (orgs[0], "echo", "Echo", "Print the input line unchanged.", [("hello\n", "hello\n")]),
            (orgs[1], "double", "Double", "Read an integer and print twice its value.", [("4\n", "8\n")]),
        ]
        for org, slug, title, statement, cases in problems:
            problem = Problem(organization_id=org.id, slug=slug, title=title)
            session.add(problem)
            await session.flush()
            version = ProblemVersion(problem_id=problem.id, version=1, statement=statement)
            session.add(version)
            await session.flush()
            suite = TestSuite(problem_version_id=version.id, version=1)
            session.add(suite)
            await session.flush()
            session.add_all(TestCase(suite_id=suite.id, input=inp, expected_output=out, ordinal=i)
                            for i, (inp, out) in enumerate(cases, 1))
        await session.commit()
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
