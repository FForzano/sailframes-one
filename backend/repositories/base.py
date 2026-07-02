"""The ``Repositories`` facade.

One repository per aggregate. Reads return SQLAlchemy ORM rows (``db/models``);
callers use their attributes directly and ``.to_dict()`` for the wire. Writes
take plain dicts / kwargs. ``get_repos()`` (``__init__.py``) builds this facade;
concrete repos are plain classes — no abstract interface layer or domain/ORM
translator, since there is a single Postgres backend.

Note on listing: where the code keeps a lightweight summary (races), the repo
exposes ``list_summaries()`` returning summary dicts, alongside ``get()`` for the
full row.
"""


class Repositories:
    """Facade bundling one repo per aggregate."""

    def __init__(
        self,
        regattas,
        racedays,
        races,
        boats,
        sessions,
        users,
        auth_tokens,
        clubs,
        groups,
        devices,
    ):
        self.regattas = regattas
        self.racedays = racedays
        self.races = races
        self.boats = boats
        self.sessions = sessions
        self.users = users
        self.auth_tokens = auth_tokens
        self.clubs = clubs
        self.groups = groups
        self.devices = devices
