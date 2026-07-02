"""SQLAlchemy declarative base + a generic ``to_dict()`` for the wire.

ISO timestamps/dates are stored as strings so the JSON wire format is stable.
``to_dict()`` serializes an ORM row to the response shape the API emits: every
column, minus ``__wire_exclude__`` (secrets / child-table bookkeeping), plus any
embedded relationships listed in ``__wire_children__`` ({orm_attr: wire_key}).
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
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
