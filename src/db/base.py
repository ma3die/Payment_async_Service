import uuid
from datetime import datetime

from sqlalchemy import UUID, DateTime, MetaData, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from config import DB_NAMING_CONVENTION, ModelIDType


class AbsBase(DeclarativeBase):
    __abstract__ = True
    metadata = MetaData(naming_convention=DB_NAMING_CONVENTION)

    def __repr__(self) -> str:
        identity = getattr(self, "id", None)
        return f"{type(self).__name__}(id={identity})"


class BaseModel(AbsBase):
    __abstract__ = True

    id: Mapped[ModelIDType] = mapped_column(
        UUID,
        primary_key=True,
        index=True,
        default=uuid.uuid4,
        comment="Identifier",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        nullable=False,
        comment="Creation timestamp",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="Last update timestamp",
    )
