"""SQLite storage: connections, transactions, and schema migrations.

Migrations are numbered SQL files in the ``migrations`` package directory
(``0001_initial.sql``, ``0002_...``). The applied version is tracked in
``PRAGMA user_version``; each migration runs in its own transaction.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path

logger = logging.getLogger(__name__)

# STRICT tables need SQLite 3.37.
MIN_SQLITE_VERSION = (3, 37, 0)
BUSY_TIMEOUT_S = 10.0

_MIGRATION_NAME = re.compile(r"^(\d{4})_[a-z0-9_]+\.sql$")


class DatabaseError(Exception):
    """The database cannot be opened or migrated."""


@dataclass(frozen=True, slots=True)
class Migration:
    version: int
    name: str
    sql: str


def connect(db_file: Path) -> sqlite3.Connection:
    """Open a connection with the project's standard settings.

    The connection is in autocommit mode; group writes with :func:`transaction`.
    """
    if sqlite3.sqlite_version_info < MIN_SQLITE_VERSION:
        required = ".".join(map(str, MIN_SQLITE_VERSION))
        raise DatabaseError(
            f"SQLite {required}+ is required, found {sqlite3.sqlite_version}; upgrade Python"
        )
    conn = sqlite3.connect(db_file, timeout=BUSY_TIMEOUT_S, isolation_level=None)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA foreign_keys = ON")
    except BaseException:
        conn.close()
        raise
    return conn


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Run the block in a write transaction; commit on success, roll back on error."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    conn.execute("COMMIT")


def load_migrations() -> list[Migration]:
    """Return the bundled migrations in order, checking that versions are 1..N."""
    migrations = []
    for resource in files("reddit_prospect_radar.migrations").iterdir():
        match = _MIGRATION_NAME.match(resource.name)
        if match:
            migrations.append(
                Migration(
                    version=int(match.group(1)),
                    name=resource.name,
                    sql=resource.read_text(encoding="utf-8"),
                )
            )
    migrations.sort(key=lambda migration: migration.version)
    versions = [migration.version for migration in migrations]
    if versions != list(range(1, len(migrations) + 1)):
        raise DatabaseError(f"migration versions must be contiguous from 1, found {versions}")
    return migrations


def schema_version(conn: sqlite3.Connection) -> int:
    version: int = conn.execute("PRAGMA user_version").fetchone()[0]
    return version


def migrate(conn: sqlite3.Connection) -> int:
    """Apply pending migrations and return the resulting schema version."""
    migrations = load_migrations()
    latest = migrations[-1].version if migrations else 0
    current = schema_version(conn)
    if current > latest:
        raise DatabaseError(
            f"database schema version {current} is newer than this program supports "
            f"({latest}); upgrade the program"
        )
    for migration in migrations[current:]:
        logger.info("Applying migration %s", migration.name)
        # executescript() runs outside Python's transaction handling, so the
        # transaction is part of the script itself.
        script = (
            f"BEGIN IMMEDIATE;\n{migration.sql}\n"
            f"PRAGMA user_version = {migration.version};\nCOMMIT;"
        )
        try:
            conn.executescript(script)
        except sqlite3.Error as exc:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise DatabaseError(f"migration {migration.name} failed: {exc}") from exc
    return latest


def initialize(db_file: Path) -> int:
    """Create the database if needed, bring its schema up to date, return the version."""
    db_file.parent.mkdir(parents=True, exist_ok=True)
    with closing(connect(db_file)) as conn:
        return migrate(conn)
