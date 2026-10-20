from uuid import UUID

from pydantic import BaseModel, Field

from enums.payment import PaymentEvent


class PaymentNewEvent(BaseModel):
    """Сообщение очереди payments.new."""

    payment_id: UUID
    event_type: PaymentEvent = Field(default=PaymentEvent.NEW)
