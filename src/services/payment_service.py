from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import (
    IdempotencyConflictError,
    InvalidIdempotencyKeyError,
    PaymentNotFoundError,
)
from enums.payment import OutboxStatus, PaymentEvent, PaymentStatus
from models.outbox import OutboxEvent
from models.payment import Payment
from schemas.messages import PaymentNewEvent
from schemas.payment import PaymentCreate
from services.request_hash import payment_request_hash


class PaymentService:
    """Создаёт платёж и событие outbox в одной транзакции."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_payment(self, data: PaymentCreate, idempotency_key: str) -> Payment:
        idempotency_key = idempotency_key.strip()
        if not idempotency_key:
            raise InvalidIdempotencyKeyError()

        digest = payment_request_hash(data)
        existing = await self._find_by_idempotency_key(idempotency_key)
        if existing is not None:
            self._ensure_same_request(existing, digest)
            return existing

        payment = Payment(
            amount=data.amount,
            currency=data.currency,
            description=data.description,
            payment_metadata=data.metadata,
            status=PaymentStatus.PENDING,
            idempotency_key=idempotency_key,
            request_hash=digest,
            webhook_url=str(data.webhook_url),
        )
        self._session.add(payment)
        try:
            await self._session.flush()
            self._session.add(self._new_event(payment))
            await self._session.commit()
        except IntegrityError:
            await self._session.rollback()
            existing = await self._find_by_idempotency_key(idempotency_key)
            if existing is not None:
                self._ensure_same_request(existing, digest)
                return existing
            raise

        await self._session.refresh(payment)
        return payment

    async def get_payment(self, payment_id: UUID) -> Payment:
        payment = await self._session.get(Payment, payment_id)
        if payment is None:
            raise PaymentNotFoundError()
        return payment

    async def _find_by_idempotency_key(self, idempotency_key: str) -> Payment | None:
        result = await self._session.execute(
            select(Payment).where(Payment.idempotency_key == idempotency_key)
        )
        return result.scalar_one_or_none()

    @staticmethod
    def _ensure_same_request(existing: Payment, digest: str) -> None:
        if existing.request_hash not in (None, digest):
            raise IdempotencyConflictError()

    @staticmethod
    def _new_event(payment: Payment) -> OutboxEvent:
        payload = PaymentNewEvent(payment_id=payment.id).model_dump(mode="json")
        return OutboxEvent(
            event_type=PaymentEvent.NEW.value,
            payload=payload,
            status=OutboxStatus.PENDING,
        )
