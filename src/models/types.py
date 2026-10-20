from enum import Enum

from sqlalchemy import Enum as SqlEnum


def pg_enum(enum_cls: type[Enum], name: str) -> SqlEnum:
    """PostgreSQL ENUM, в котором хранятся значения, а не имена членов."""
    return SqlEnum(
        enum_cls,
        name=name,
        native_enum=True,
        values_callable=lambda items: [item.value for item in items],
    )
