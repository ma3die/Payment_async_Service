"""outbox claim statuses and payment request hash

Revision ID: 0002_outbox_claim
Revises: 0001_payments_outbox
Create Date: 2026-10-19

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_outbox_claim"
down_revision: str | Sequence[str] | None = "0001_payments_outbox"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE outbox_status ADD VALUE IF NOT EXISTS 'publishing'")
    op.execute("ALTER TYPE outbox_status ADD VALUE IF NOT EXISTS 'failed'")
    op.add_column("payments", sa.Column("request_hash", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("payments", "request_hash")
