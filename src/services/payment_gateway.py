import asyncio
import random
from collections.abc import Awaitable, Callable
from typing import Protocol

from config import settings
from enums.payment import PaymentStatus


class RandomSource(Protocol):
    def random(self) -> float:
        """Случайное число от 0 до 1."""

    def uniform(self, a: float, b: float) -> float:
        """Случайное число в диапазоне."""


class SimulatedPaymentGateway:
    """Эмуляция внешнего шлюза: 2–5 секунд, 90% успех."""

    def __init__(
            self,
            min_delay_seconds: float | None = None,
            max_delay_seconds: float | None = None,
            success_rate: float | None = None,
            random_source: RandomSource | None = None,
            sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._min_delay_seconds = (
            settings.gateway.GATEWAY_MIN_DELAY_SECONDS
            if min_delay_seconds is None
            else min_delay_seconds
        )
        self._max_delay_seconds = (
            settings.gateway.GATEWAY_MAX_DELAY_SECONDS
            if max_delay_seconds is None
            else max_delay_seconds
        )
        self._success_rate = settings.gateway.GATEWAY_SUCCESS_RATE if success_rate is None else success_rate
        self._random = random_source or random.Random()
        self._sleep = sleep

    async def authorize(self) -> PaymentStatus:
        delay = self._random.uniform(self._min_delay_seconds, self._max_delay_seconds)
        await self._sleep(delay)
        if self._random.random() < self._success_rate:
            return PaymentStatus.SUCCEEDED
        return PaymentStatus.FAILED
