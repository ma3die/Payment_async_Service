import pytest

from enums.payment import PaymentStatus
from services.payment_gateway import SimulatedPaymentGateway


class ScriptedRandom:
    def __init__(self, delays: list[float], values: list[float]) -> None:
        self._delays = iter(delays)
        self._values = iter(values)

    def uniform(self, start: float, end: float) -> float:
        return next(self._delays)

    def random(self) -> float:
        return next(self._values)


@pytest.mark.asyncio
async def test_gateway_returns_success_and_waits_scripted_delay():
    delays = []

    async def sleep(delay: float) -> None:
        delays.append(delay)

    gateway = SimulatedPaymentGateway(
        min_delay_seconds=2,
        max_delay_seconds=5,
        success_rate=0.9,
        random_source=ScriptedRandom([3.5], [0.1]),
        sleep=sleep,
    )

    assert await gateway.authorize() is PaymentStatus.SUCCEEDED
    assert delays == [3.5]


@pytest.mark.asyncio
async def test_gateway_returns_failure_below_success_rate():
    async def sleep(delay: float) -> None:
        return None

    gateway = SimulatedPaymentGateway(
        min_delay_seconds=2,
        max_delay_seconds=5,
        success_rate=0.9,
        random_source=ScriptedRandom([2], [0.95]),
        sleep=sleep,
    )

    assert await gateway.authorize() is PaymentStatus.FAILED
