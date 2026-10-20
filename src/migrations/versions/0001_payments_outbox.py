"""payments and outbox

Revision ID: 0001_payments_outbox
Revises:
Create Date: 2026-10-19

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_payments_outbox"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

payment_status = postgresql.ENUM(
    "pending",
    "succeeded",
    "failed",
    name="payment_status",
    create_type=False,
)
payment_currency = postgresql.ENUM(
    "RUB",
    "USD",
    "EUR",
    name="payment_currency",
    create_type=False,
)
outbox_status = postgresql.ENUM(
    "pending",
    "published",
    name="outbox_status",
    create_type=False,
)


def upgrade() -> None:
    payment_status.create(op.get_bind(), checkfirst=True)
    payment_currency.create(op.get_bind(), checkfirst=True)
    outbox_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", payment_currency, nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("status", payment_status, server_default=sa.text("'pending'"), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("webhook_url", sa.String(length=2048), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("amount > 0", name="ck__payments__amount_positive"),
        sa.PrimaryKeyConstraint("id", name="pk__payments"),
        sa.UniqueConstraint("idempotency_key", name="uq__payments__idempotency_key"),
    )
    op.create_index("ix__payments__id", "payments", ["id"])

    op.create_table(
        "outbox",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("status", outbox_status, server_default=sa.text("'pending'"), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk__outbox"),
    )
    op.create_index("ix__outbox__id", "outbox", ["id"])
    op.create_index("ix__outbox__status", "outbox", ["status"])


def downgrade() -> None:
    op.drop_index("ix__outbox__status", table_name="outbox")
    op.drop_index("ix__outbox__id", table_name="outbox")
    op.drop_table("outbox")
    op.drop_index("ix__payments__id", table_name="payments")
    op.drop_table("payments")
    outbox_status.drop(op.get_bind(), checkfirst=True)
    payment_currency.drop(op.get_bind(), checkfirst=True)
    payment_status.drop(op.get_bind(), checkfirst=True)
