"""The ``Repositories`` facade.

One repository per aggregate. Reads return SQLAlchemy ORM rows (``db/models``);
callers use their attributes directly and ``.to_dict()`` for the wire. Writes
take plain dicts / kwargs. ``get_repos()`` (``__init__.py``) builds this facade;
concrete repos are plain classes — no abstract interface layer or domain/ORM
translator, since there is a single Postgres backend.

er-project phase: only the repos auth/RBAC needs are built (users, auth_tokens,
clubs, groups, boats). The rest default to ``None`` until the api-project phase
rewrites them against the new schema (sessions/activities/uploads, devices
claim flow, regattas/races/results).
"""


class Repositories:
    """Facade bundling one repo per aggregate."""

    def __init__(
        self,
        *,
        users,
        auth_tokens,
        clubs,
        groups,
        boats,
        regattas=None,
        racedays=None,
        races=None,
        sessions=None,
        devices=None,
    ):
        self.users = users
        self.auth_tokens = auth_tokens
        self.clubs = clubs
        self.groups = groups
        self.boats = boats
        self.regattas = regattas
        self.racedays = racedays
        self.races = races
        self.sessions = sessions
        self.devices = devices
