from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import closing
from pathlib import Path

import pytest

from reddit_prospect_radar import db

EXPECTED_TABLES = {"posts", "scores", "notifications", "feedback", "outcomes", "drafts", "runs"}


@pytest.fixture
def db_file(tmp_path: Path) -> Path:
    path = tmp_path / "data" / "test.db"
    db.initialize(path)
    return path


@pytest.fixture
def conn(db_file: Path) -> Iterator[sqlite3.Connection]:
    with closing(db.connect(db_file)) as connection:
        yield connection


def _insert_post(conn: sqlite3.Connection, post_id: str = "t3_abc123") -> None:
    conn.execute(
        "INSERT INTO posts (id, subreddit, title, url, first_seen_utc, source)"
        " VALUES (?, 'SaaS', 'title', 'https://example.com', 0, 'subreddit_new:saas')",
        (post_id,),
    )


def test_initialize_creates_schema(conn: sqlite3.Connection) -> None:
    tables = {
        row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }

    assert tables >= EXPECTED_TABLES
    assert db.schema_version(conn) == len(db.load_migrations())


def test_initialize_is_idempotent(db_file: Path) -> None:
    assert db.initialize(db_file) == len(db.load_migrations())


def test_connection_settings(conn: sqlite3.Connection) -> None:
    assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert conn.isolation_level is None


def test_foreign_keys_are_enforced(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
        conn.execute("INSERT INTO feedback (post_id, label, created_utc) VALUES ('t3_x', 1, 0)")


@pytest.mark.parametrize(
    "statement",
    [
        "INSERT INTO feedback (post_id, label, created_utc) VALUES ('t3_abc123', 2, 0)",
        "INSERT INTO scores (post_id, stage, score, created_utc)"
        " VALUES ('t3_abc123', 'vibes', 0.5, 0)",
        "INSERT INTO runs (started_utc, status) VALUES (0, 'fine')",
        "INSERT INTO posts (id, subreddit, title, url, first_seen_utc, source)"
        " VALUES ('abc123', 'SaaS', 't', 'u', 0, 's')",
        "INSERT INTO posts (id, subreddit, title, url, first_seen_utc, source)"
        " VALUES ('t3_x', 'SaaS', 't', 'u', 'yesterday', 's')",
    ],
)
def test_constraints_reject_invalid_rows(conn: sqlite3.Connection, statement: str) -> None:
    _insert_post(conn)

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(statement)


def test_transaction_commits(conn: sqlite3.Connection) -> None:
    with db.transaction(conn):
        _insert_post(conn)

    assert conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0] == 1


def test_transaction_rolls_back_on_error(conn: sqlite3.Connection) -> None:
    def write_then_fail() -> None:
        with db.transaction(conn):
            _insert_post(conn)
            raise RuntimeError

    with pytest.raises(RuntimeError):
        write_then_fail()

    assert conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0] == 0
    assert not conn.in_transaction


def test_newer_schema_is_refused(db_file: Path) -> None:
    with closing(db.connect(db_file)) as connection:
        connection.execute("PRAGMA user_version = 999")

    with pytest.raises(db.DatabaseError, match="newer than this program supports"):
        db.initialize(db_file)


def test_failed_migration_rolls_back(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    broken = [
        db.Migration(1, "0001_ok.sql", "CREATE TABLE a (x INTEGER);"),
        db.Migration(2, "0002_broken.sql", "CREATE TABLE b (x INTEGER); NOT VALID SQL;"),
    ]
    monkeypatch.setattr(db, "load_migrations", lambda: broken)
    db_file = tmp_path / "broken.db"

    with pytest.raises(db.DatabaseError, match=r"0002_broken\.sql"):
        db.initialize(db_file)

    with closing(db.connect(db_file)) as connection:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master")}
        assert db.schema_version(connection) == 1
        assert "a" in tables
        assert "b" not in tables


def test_bundled_migrations_are_contiguous() -> None:
    migrations = db.load_migrations()

    assert [m.version for m in migrations] == list(range(1, len(migrations) + 1))
    assert migrations[0].name == "0001_initial.sql"
