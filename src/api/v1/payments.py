from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import require_api_key
from db.session import get_async_session
from models.payment import Payment
from schemas.payment import PaymentAccepted, PaymentCreate, PaymentDetails
from services.payment_service import PaymentService

router = APIRouter(
    prefix="/payments",
    tags=["payments"],
    dependencies=[Depends(require_api_key)],
)

IdempotencyKey = Annotated[
    str,
    Header(alias="Idempotency-Key", min_length=1, max_length=255),
]
DatabaseSession = Annotated[AsyncSession, Depends(get_async_session)]


@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=PaymentAccepted)
async def create_payment(
        data: PaymentCreate,
        idempotency_key: IdempotencyKey,
        session: DatabaseSession,
) -> PaymentAccepted:
    """Принимает платёж в обработку. Повтор с тем же ключом возвращает уже созданный платёж."""
    payment = await PaymentService(session).create_payment(data, idempotency_key)
    return _accepted(payment)


@router.get("/{payment_id}", response_model=PaymentDetails)
async def get_payment(payment_id: UUID, session: DatabaseSession) -> PaymentDetails:
    """Возвращает текущее состояние платежа."""
    payment = await PaymentService(session).get_payment(payment_id)
    return _details(payment)


def _accepted(payment: Payment) -> PaymentAccepted:
    return PaymentAccepted(
        payment_id=payment.id,
        status=payment.status,
        created_at=payment.created_at,
    )


def _details(payment: Payment) -> PaymentDetails:
    return PaymentDetails(
        payment_id=payment.id,
        amount=payment.amount,
        currency=payment.currency,
        description=payment.description,
        metadata=payment.payment_metadata,
        status=payment.status,
        idempotency_key=payment.idempotency_key,
        webhook_url=payment.webhook_url,
        created_at=payment.created_at,
        processed_at=payment.processed_at,
    )
