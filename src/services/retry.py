import asyncio
from collections.abc import Awaitable, Callable


class RetryPolicy:
    """Считает задержку перед следующей попыткой: base, base*2, base*4."""

    def __init__(self, max_attempts: int, base_delay_seconds: float) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts должен быть не меньше 1")
        if base_delay_seconds < 0:
            raise ValueError("base_delay_seconds не может быть отрицательным")
        self.max_attempts = max_attempts
        self.base_delay_seconds = base_delay_seconds

    def delay_after(self, attempt: int) -> float | None:
        """Возвращает паузу после неудачной попытки или None, если попытки закончились."""
        if attempt < 1:
            raise ValueError("attempt должен быть не меньше 1")
        if attempt >= self.max_attempts:
            return None
        return self.base_delay_seconds * (2 ** (attempt - 1))


class AttemptRunner:
    """Повторяет операцию, пока политика не исчерпает попытки."""

    def __init__(
            self,
            policy: RetryPolicy,
            retryable: tuple[type[Exception], ...] = (Exception,),
            sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._policy = policy
        self._retryable = retryable
        self._sleep = sleep

    async def run(self, operation: Callable[[], Awaitable[None]]) -> bool:
        for attempt in range(1, self._policy.max_attempts + 1):
            try:
                await operation()
            except self._retryable:
                delay = self._policy.delay_after(attempt)
                if delay is None:
                    return False
                await self._sleep(delay)
                continue
            return True
        return False
