from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, Integer, String, Text, UniqueConstraint, Index, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Role(str, Enum):
    PARTICIPANT = "participant"
    ORGANIZER = "organizer"


class OrgRole(str, Enum):
    MEMBER = "member"
    ORGANIZER = "organizer"


class AttemptStatus(str, Enum):
    QUEUE = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Verdict(str, Enum):
    ACCEPTED = "accepted"
    WRONG_ANSWER = "wrong_answer"
    COMPILATION_ERROR = "compilation_error"
    RUNTIME_ERROR = "runtime_error"
    TIME_LIMIT = "time_limit"
    EXCESSIVE_OUTPUT = "excessive_output"
    JUDGE_INFRA_FAILURE = "judge_infrastructure_failure"


class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    memberships: Mapped[list["Membership"]] = relationship(back_populates="organization")


class Identity(Base):
    __tablename__ = "identities"
    id: Mapped[int] = mapped_column(primary_key=True)
    external_id: Mapped[str] = mapped_column(String(100), unique=True)
    display_name: Mapped[str] = mapped_column(String(200))
    memberships: Mapped[list["Membership"]] = relationship(back_populates="identity")


class Membership(Base):
    __tablename__ = "memberships"
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), primary_key=True)
    identity_id: Mapped[int] = mapped_column(ForeignKey("identities.id"), primary_key=True)
    role: Mapped[OrgRole] = mapped_column(SAEnum(OrgRole), nullable=False)
    organization: Mapped[Organization] = relationship(back_populates="memberships")
    identity: Mapped[Identity] = relationship(back_populates="memberships")


class Contest(Base):
    __tablename__ = "contests"
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Participation(Base):
    __tablename__ = "participations"
    contest_id: Mapped[int] = mapped_column(ForeignKey("contests.id"), primary_key=True)
    identity_id: Mapped[int] = mapped_column(ForeignKey("identities.id"), primary_key=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Problem(Base):
    __tablename__ = "problems"
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    slug: Mapped[str] = mapped_column(String(100), index=True)
    title: Mapped[str] = mapped_column(String(300))


class ProblemVersion(Base):
    __tablename__ = "problem_versions"
    id: Mapped[int] = mapped_column(primary_key=True)
    problem_id: Mapped[int] = mapped_column(ForeignKey("problems.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    statement: Mapped[str] = mapped_column(Text)
    __table_args__ = (UniqueConstraint("problem_id", "version", name="uq_problem_version"),)


class TestSuite(Base):
    __tablename__ = "test_suites"
    id: Mapped[int] = mapped_column(primary_key=True)
    problem_version_id: Mapped[int] = mapped_column(ForeignKey("problem_versions.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    __table_args__ = (UniqueConstraint("problem_version_id", "version", name="uq_suite_version"),)


class TestCase(Base):
    __tablename__ = "test_cases"
    id: Mapped[int] = mapped_column(primary_key=True)
    suite_id: Mapped[int] = mapped_column(ForeignKey("test_suites.id"), index=True)
    input: Mapped[str] = mapped_column(Text)
    expected_output: Mapped[str] = mapped_column(Text)
    ordinal: Mapped[int] = mapped_column(Integer)
    __table_args__ = (UniqueConstraint("suite_id", "ordinal", name="uq_test_ordinal"),)


class Submission(Base):
    __tablename__ = "submissions"
    id: Mapped[int] = mapped_column(primary_key=True)
    contest_id: Mapped[int] = mapped_column(ForeignKey("contests.id"), index=True)
    identity_id: Mapped[int] = mapped_column(ForeignKey("identities.id"), index=True)
    problem_id: Mapped[int] = mapped_column(ForeignKey("problems.id"), index=True)
    problem_version_id: Mapped[int] = mapped_column(ForeignKey("problem_versions.id"))
    suite_id: Mapped[int] = mapped_column(ForeignKey("test_suites.id"))
    language: Mapped[str] = mapped_column(String(30))
    code: Mapped[str] = mapped_column(Text)
    runtime_config: Mapped[dict] = mapped_column(JSONB)
    idempotency_key: Mapped[str] = mapped_column(String(200))
    request_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    authoritative_attempt_id: Mapped[int | None] = mapped_column(ForeignKey("judging_attempts.id", use_alter=True, name="fk_authoritative_attempt"), nullable=True)
    wrong_attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__ = (
        UniqueConstraint("contest_id", "identity_id", "idempotency_key", name="uq_submission_idempotency"),
        Index("ix_submission_leaderboard", "contest_id", "identity_id", "accepted_at"),
    )


class JudgingAttempt(Base):
    __tablename__ = "judging_attempts"
    id: Mapped[int] = mapped_column(primary_key=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("submissions.id"), index=True)
    attempt_number: Mapped[int] = mapped_column(Integer)
    status: Mapped[AttemptStatus] = mapped_column(SAEnum(AttemptStatus), default=AttemptStatus.QUEUE, index=True)
    verdict: Mapped[Verdict | None] = mapped_column(SAEnum(Verdict), nullable=True)
    problem_version_id: Mapped[int] = mapped_column(ForeignKey("problem_versions.id"))
    suite_id: Mapped[int] = mapped_column(ForeignKey("test_suites.id"))
    language: Mapped[str] = mapped_column(String(30))
    code: Mapped[str] = mapped_column(Text)
    runtime_config: Mapped[dict] = mapped_column(JSONB)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    lease_owner: Mapped[str | None] = mapped_column(String(100), nullable=True)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    judge_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    __table_args__ = (UniqueConstraint("submission_id", "attempt_number", name="uq_attempt_number"),)


class DomainError(Exception):
    pass


class ConflictError(DomainError):
    pass


class ForbiddenError(DomainError):
    pass


class NotFoundError(DomainError):
    pass
