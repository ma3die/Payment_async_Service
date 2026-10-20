import asyncio

import pytest

from core.exceptions import RetryableError
from services.retry import AttemptRunner, RetryPolicy


def test_delay_doubles_until_attempts_end():
    policy = RetryPolicy(max_attempts=3, base_delay_seconds=1)

    assert policy.delay_after(1) == 1
    assert policy.delay_after(2) == 2
    assert policy.delay_after(3) is None


def test_policy_rejects_invalid_attempts():
    with pytest.raises(ValueError):
        RetryPolicy(max_attempts=0, base_delay_seconds=1)


@pytest.mark.asyncio
async def test_runner_retries_then_succeeds():
    delays = []

    async def sleep(delay: float) -> None:
        delays.append(delay)

    attempts = {"count": 0}

    async def operation() -> None:
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise RetryableError("temporary")

    runner = AttemptRunner(
        RetryPolicy(max_attempts=3, base_delay_seconds=1),
        retryable=(RetryableError,),
        sleep=sleep,
    )

    assert await runner.run(operation) is True
    assert attempts["count"] == 3
    assert delays == [1, 2]


@pytest.mark.asyncio
async def test_runner_returns_false_when_attempts_are_exhausted():
    runner = AttemptRunner(
        RetryPolicy(max_attempts=3, base_delay_seconds=0),
        retryable=(RetryableError,),
        sleep=asyncio.sleep,
    )

    async def operation() -> None:
        raise RetryableError("temporary")

    assert await runner.run(operation) is False


@pytest.mark.asyncio
async def test_runner_does_not_retry_unknown_error():
    runner = AttemptRunner(
        RetryPolicy(max_attempts=3, base_delay_seconds=0),
        retryable=(RetryableError,),
        sleep=asyncio.sleep,
    )

    async def operation() -> None:
        raise RuntimeError("permanent")

    with pytest.raises(RuntimeError):
        await runner.run(operation)
