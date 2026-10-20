from datetime import datetime

from sqlalchemy import DateTime, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from db.base import BaseModel
from enums.payment import OutboxStatus
from models.types import pg_enum


class OutboxEvent(BaseModel):
    """Событие, которое нужно гарантированно опубликовать в брокер."""

    __tablename__ = "outbox"

    event_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="Тип события",
    )
    payload: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        comment="Тело события",
    )
    status: Mapped[OutboxStatus] = mapped_column(
        pg_enum(OutboxStatus, "outbox_status"),
        nullable=False,
        default=OutboxStatus.PENDING,
        server_default=text("'pending'"),
        index=True,
        comment="Статус публикации",
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Момент успешной публикации",
    )
