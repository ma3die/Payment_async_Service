from enum import Enum


class Currency(str, Enum):
    """Валюта платежа."""

    RUB = "RUB"
    USD = "USD"
    EUR = "EUR"


class PaymentStatus(str, Enum):
    """Статус платежа."""

    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class OutboxStatus(str, Enum):
    """Статус публикации события из outbox."""

    PENDING = "pending"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    FAILED = "failed"


class PaymentEvent(str, Enum):
    """Тип события, которое публикуется в брокер."""

    NEW = "payments.new"
