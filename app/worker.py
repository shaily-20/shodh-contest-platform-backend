import asyncio
import logging
import socket
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import aliased

from app.config import settings
from app.db import SessionLocal
from app.models import (
    AttemptStatus,
    JudgingAttempt,
    Submission,
    TestCase,
    Verdict,
)
from app.runner import RunnerInfrastructureError, run_python

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("shodh.worker")


def judge(code: str, cases: list[TestCase]) -> tuple[Verdict, str]:
    for case in cases:
        try:
            stdout, stderr, _, timed_out = run_python(code, case.input)
        except RunnerInfrastructureError as exc:
            logger.exception("Docker runner infrastructure failure")
            return Verdict.JUDGE_INFRA_FAILURE, str(exc)
        if timed_out:
            return Verdict.TIME_LIMIT, "Execution exceeded the configured time or output limit"
        if stderr or not stdout and case.expected_output.strip():
            # Python tracebacks are emitted to stderr by the isolated runtime.
            if stderr:
                return Verdict.RUNTIME_ERROR, stderr[:4000]
        if stdout.strip() != case.expected_output.strip():
            return Verdict.WRONG_ANSWER, f"Failed test case {case.ordinal}"
    return Verdict.ACCEPTED, "All test cases passed"


async def claim_attempt() -> int | None:
    now = datetime.now(timezone.utc)
    async with SessionLocal() as session:
        attempt = await session.scalar(
            select(JudgingAttempt)
            .where(
                (JudgingAttempt.status == AttemptStatus.QUEUE)
                | ((JudgingAttempt.status == AttemptStatus.RUNNING) & (JudgingAttempt.lease_until < now))
            )
            .order_by(JudgingAttempt.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if attempt is None:
            return None
        attempt.status = AttemptStatus.RUNNING
        attempt.lease_owner = settings.worker_id or socket.gethostname()
        attempt.lease_until = now + timedelta(seconds=max(30, settings.runner_timeout_seconds * 120))
        attempt.started_at = now
        await session.commit()
        return attempt.id


async def process_attempt(attempt_id: int) -> None:
    async with SessionLocal() as session:
        attempt = await session.get(JudgingAttempt, attempt_id)
        if attempt is None:
            return
        cases = list(await session.scalars(
            select(TestCase).where(TestCase.suite_id == attempt.suite_id).order_by(TestCase.ordinal)
        ))
        code = attempt.code
        language = attempt.language
    if language not in {"python", "python3"}:
        verdict, detail = Verdict.COMPILATION_ERROR, "Unsupported language"
    elif not cases:
        verdict, detail = Verdict.JUDGE_INFRA_FAILURE, "Test suite is empty"
    else:
        verdict, detail = await asyncio.to_thread(judge, code, cases)
    now = datetime.now(timezone.utc)
    async with SessionLocal() as session:
        attempt = await session.get(JudgingAttempt, attempt_id)
        if attempt is None:
            return
        attempt.verdict = verdict
        attempt.status = AttemptStatus.COMPLETED
        attempt.completed_at = now
        attempt.lease_until = None
        attempt.judge_detail = detail[:4000]
        submission = await session.get(Submission, attempt.submission_id)
        if submission is not None and verdict == Verdict.ACCEPTED:
            submission.accepted_at = now
            submission.authoritative_attempt_id = attempt.id
        await session.commit()
    logger.info("Judged attempt %s: %s", attempt_id, verdict.value)


async def run_worker() -> None:
    logger.info("Judging worker %s started (Docker image: %s)", settings.worker_id, settings.runner_image)
    while True:
        try:
            attempt_id = await claim_attempt()
            if attempt_id is None:
                await asyncio.sleep(1)
                continue
            await process_attempt(attempt_id)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Worker loop error")
            await asyncio.sleep(2)


if __name__ == "__main__":
    asyncio.run(run_worker())
