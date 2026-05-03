"""
Database engine, session factory, and schema initialisation for SCOUT.

Usage
-----
    from pathlib import Path
    from scout.db import get_engine, get_session_factory, init_db

    engine = get_engine(Path("~/.scout/scout.db").expanduser())
    init_db(engine)
    SessionLocal = get_session_factory(engine)

    with SessionLocal() as session:
        ...
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker


def get_engine(db_path: Path) -> Engine:
    """Return a SQLite engine for *db_path*, creating parent directories as needed."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )


def get_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Return a configured :class:`sessionmaker` bound to *engine*."""
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


# ---------------------------------------------------------------------------
# Raw SQL schema — matches Section 9 of the SCOUT MVP design spec.
# Using CREATE TABLE / INDEX IF NOT EXISTS so init_db() is idempotent.
# ---------------------------------------------------------------------------

_DDL_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS investigations (
        id              TEXT PRIMARY KEY,
        mode            TEXT NOT NULL,
        target          TEXT NOT NULL,
        target_type     TEXT NOT NULL,
        created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        completed_at    TIMESTAMP,
        status          TEXT NOT NULL DEFAULT 'running',
        note            TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS source_runs (
        id               TEXT PRIMARY KEY,
        investigation_id TEXT NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
        source_name      TEXT NOT NULL,
        started_at       TIMESTAMP NOT NULL,
        finished_at      TIMESTAMP,
        status           TEXT NOT NULL,
        error_message    TEXT,
        cache_hit        BOOLEAN NOT NULL DEFAULT 0
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS nodes (
        id               TEXT NOT NULL,
        investigation_id TEXT NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
        type             TEXT NOT NULL,
        label            TEXT NOT NULL,
        attrs_json       TEXT NOT NULL DEFAULT '{}',
        discovered_by    TEXT NOT NULL,
        PRIMARY KEY (id, investigation_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS edges (
        id               TEXT PRIMARY KEY,
        investigation_id TEXT NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
        src_node_id      TEXT NOT NULL,
        dst_node_id      TEXT NOT NULL,
        relation         TEXT NOT NULL,
        discovered_by    TEXT NOT NULL,
        UNIQUE(investigation_id, src_node_id, dst_node_id, relation)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS response_cache (
        id            TEXT PRIMARY KEY,
        source_name   TEXT NOT NULL,
        request_key   TEXT NOT NULL,
        response_json TEXT NOT NULL,
        fetched_at    TIMESTAMP NOT NULL,
        expires_at    TIMESTAMP NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_cache_expires ON response_cache(expires_at)",
    "CREATE INDEX IF NOT EXISTS idx_cache_lookup  ON response_cache(source_name, request_key)",
]


def init_db(engine: Engine) -> None:
    """Create all SCOUT tables and indexes using raw SQL.

    Safe to call multiple times — every statement uses ``IF NOT EXISTS``.
    """
    with engine.begin() as conn:
        for statement in _DDL_STATEMENTS:
            conn.execute(text(statement))
