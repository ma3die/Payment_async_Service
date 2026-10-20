import json
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    field_serializer,
    field_validator,
)

from enums.payment import Currency, PaymentStatus

MAX_METADATA_BYTES = 4096
MAX_WEBHOOK_URL_LENGTH = 2048


class PaymentCreate(BaseModel):
    """Запрос на создание платежа."""

    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    currency: Currency
    description: str = Field(min_length=1, max_length=500)
    metadata: dict[str, Any] = Field(default_factory=dict)
    webhook_url: HttpUrl

    @field_validator("amount", mode="before")
    @classmethod
    def amount_rejects_float(cls, value: object) -> object:
        if isinstance(value, (bool, float)):
            raise ValueError("Сумма должна быть строкой с десятичной точкой, не JSON-числом")  # noqa: TRY004
        return value

    @field_validator("description")
    @classmethod
    def description_is_not_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Описание не может быть пустым")
        return cleaned

    @field_validator("metadata")
    @classmethod
    def metadata_has_limited_size(cls, value: dict[str, Any]) -> dict[str, Any]:
        raw = json.dumps(value, ensure_ascii=False).encode("utf-8")
        if len(raw) > MAX_METADATA_BYTES:
            raise ValueError("metadata больше 4096 байт")
        return value

    @field_validator("webhook_url")
    @classmethod
    def webhook_url_fits_column(cls, value: HttpUrl) -> HttpUrl:
        if len(str(value)) > MAX_WEBHOOK_URL_LENGTH:
            raise ValueError("webhook_url длиннее 2048 символов")
        return value


class PaymentAccepted(BaseModel):
    """Ответ на принятие платежа в обработку."""

    payment_id: UUID
    status: PaymentStatus
    created_at: datetime


class PaymentDetails(BaseModel):
    """Полная информация о платеже."""

    model_config = ConfigDict(from_attributes=True)

    payment_id: UUID
    amount: Decimal
    currency: Currency
    description: str
    metadata: dict[str, Any]
    status: PaymentStatus
    idempotency_key: str
    webhook_url: str
    created_at: datetime
    processed_at: datetime | None

    @field_serializer("amount")
    def serialize_amount(self, amount: Decimal) -> str:
        return format(amount, "f")


class WebhookPayload(BaseModel):
    """Тело уведомления, которое уходит на webhook клиента."""

    payment_id: UUID
    status: PaymentStatus
    amount: Decimal
    currency: Currency
    processed_at: datetime

    @field_serializer("amount")
    def serialize_amount(self, amount: Decimal) -> str:
        return format(amount, "f")
