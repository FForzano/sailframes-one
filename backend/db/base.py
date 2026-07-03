"""SQLAlchemy declarative base, shared mixins, and a generic ``to_dict()``.

Schema-wide conventions (er-project redesign):
- UUID primary keys (``UUIDPKMixin``): client-side ``uuid4`` so ``orm.id`` is
  readable right after ``flush()``, plus ``gen_random_uuid()`` as a server-side
  safety net for raw SQL inserts (built into Postgres 13+).
- Real TIMESTAMPTZ columns (``CreatedAtMixin``/``TimestampMixin``); no more
  ISO-string timestamps.
- Enum-like string columns are constrained with ``enum_check()`` CHECKs; the
  ``MetaData`` naming convention gives every constraint a deterministic name
  so Alembic can address them later.

``to_dict()`` serializes an ORM row to the response shape the API emits: every
column, minus ``__wire_exclude__`` (secrets / child-table bookkeeping), plus any
embedded relationships listed in ``__wire_children__`` ({orm_attr: wire_key}).
FastAPI's encoder handles ``uuid.UUID``/``datetime`` values natively.
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, MetaData, Uuid, func, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)

    # Columns left out of the wire (e.g. password_hash, child FK bookkeeping).
    __wire_exclude__: tuple = ()
    # Relationships to embed: {orm_attr: wire_key}. A list attr becomes a list
    # of child ``to_dict()``s; a scalar becomes one (or None).
    __wire_children__: dict = {}

    def to_dict(self) -> dict:
        d = {
            c.key: getattr(self, c.key)
            for c in self.__mapper__.column_attrs
            if c.key not in self.__wire_exclude__
        }
        for attr, key in self.__wire_children__.items():
            val = getattr(self, attr)
            if isinstance(val, list):
                d[key] = [x.to_dict() for x in val]
            else:
                d[key] = val.to_dict() if val is not None else None
        return d


class UUIDPKMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )


class CreatedAtMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class TimestampMixin(CreatedAtMixin):
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


def enum_check(column: str, values: tuple[str, ...], name: str | None = None) -> CheckConstraint:
    """CHECK constraint restricting a string column to a fixed set of values.

    NULL passes the CHECK (SQL three-valued logic), so the same helper works
    for nullable enum columns. With the ``ck`` naming convention the default
    name renders as ``ck_<table>_<column>_allowed``.
    """
    quoted = ", ".join(f"'{v}'" for v in values)
    return CheckConstraint(f"{column} IN ({quoted})", name=name or f"{column}_allowed")
