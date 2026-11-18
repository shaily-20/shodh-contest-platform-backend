from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)


class OrganizationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class IdentityCreate(BaseModel):
    external_id: str = Field(min_length=1, max_length=100)
    display_name: str = Field(min_length=1, max_length=200)


class IdentityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    external_id: str
    display_name: str


class ContestCreate(BaseModel):
    organization_id: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=300)
    starts_at: datetime
    ends_at: datetime

    @model_validator(mode="after")
    def validate_period(self):
        if self.starts_at >= self.ends_at:
            raise ValueError("ends_at must be later than starts_at")
        return self


class ContestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    title: str
    starts_at: datetime
    ends_at: datetime


class JoinContest(BaseModel):
    identity_id: int = Field(gt=0)


class TestCaseCreate(BaseModel):
    input: str
    expected_output: str


class ProblemCreate(BaseModel):
    slug: str = Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_-]*$")
    title: str = Field(min_length=1, max_length=300)
    statement: str = Field(min_length=1)
    test_cases: list[TestCaseCreate] = Field(min_length=1, max_length=100)


class ProblemOut(BaseModel):
    id: int
    organization_id: int
    slug: str
    title: str
    version: int
    statement: str


class SubmissionCreate(BaseModel):
    identity_id: int = Field(gt=0)
    problem_id: int = Field(gt=0)
    language: str = Field(min_length=1, max_length=30)
    code: str = Field(min_length=1, max_length=100_000)
    idempotency_key: str = Field(min_length=1, max_length=200)


class SubmissionOut(BaseModel):
    id: int
    contest_id: int
    identity_id: int
    problem_id: int
    language: str
    status: str
    verdict: str | None = None
    created_at: datetime | None = None
