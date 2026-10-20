from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, Numeric, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from db.base import BaseModel
from enums.payment import Currency, PaymentStatus
from models.types import pg_enum


class Payment(BaseModel):
    """Платёж, принятый сервисом и обработанный асинхронно."""

    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint("amount > 0", name="amount_positive"),
    )

    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        comment="Сумма платежа",
    )
    currency: Mapped[Currency] = mapped_column(
        pg_enum(Currency, "payment_currency"),
        nullable=False,
        comment="Валюта платежа",
    )
    description: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="Описание платежа",
    )
    payment_metadata: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
        comment="Дополнительные данные платежа",
    )
    status: Mapped[PaymentStatus] = mapped_column(
        pg_enum(PaymentStatus, "payment_status"),
        nullable=False,
        default=PaymentStatus.PENDING,
        server_default=text("'pending'"),
        comment="Статус обработки",
    )
    idempotency_key: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        comment="Ключ защиты от повторного создания",
    )
    request_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment="Хеш тела запроса для этого ключа",
    )
    webhook_url: Mapped[str] = mapped_column(
        String(2048),
        nullable=False,
        comment="URL уведомления о результате",
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Момент завершения обработки",
    )
