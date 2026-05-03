"""Tests for scout.db — engine, init_db(), and schema verification."""

from __future__ import annotations

from collections.abc import Generator

import pytest
from sqlalchemy import Engine, create_engine, text

from scout.db import get_engine, get_session_factory, init_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

EXPECTED_TABLES = {
    "investigations",
    "source_runs",
    "nodes",
    "edges",
    "response_cache",
}


def _existing_tables(engine: Engine) -> set[str]:
    """Return the set of user-created table names in the SQLite database."""
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table'")
        ).fetchall()
    return {row[0] for row in rows}


def _existing_indexes(engine: Engine) -> set[str]:
    """Return the set of index names in the SQLite database."""
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='index'")
        ).fetchall()
    return {row[0] for row in rows}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def memory_engine() -> Generator[Engine, None, None]:
    """In-memory SQLite engine — discarded after each test."""
    engine = create_engine("sqlite:///:memory:")
    yield engine
    engine.dispose()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_init_db_creates_all_tables(memory_engine: Engine) -> None:
    """All five expected tables must exist after init_db()."""
    init_db(memory_engine)
    assert EXPECTED_TABLES.issubset(_existing_tables(memory_engine))


def test_init_db_creates_cache_indexes(memory_engine: Engine) -> None:
    """idx_cache_expires and idx_cache_lookup must exist after init_db()."""
    init_db(memory_engine)
    indexes = _existing_indexes(memory_engine)
    assert "idx_cache_expires" in indexes
    assert "idx_cache_lookup" in indexes


def test_init_db_is_idempotent(memory_engine: Engine) -> None:
    """Calling init_db() twice must not raise any exception."""
    init_db(memory_engine)
    init_db(memory_engine)  # must not raise
    assert EXPECTED_TABLES.issubset(_existing_tables(memory_engine))


def test_get_engine_creates_in_memory_engine(tmp_path: pytest.TempPathFactory) -> None:
    """get_engine() must return a working engine and create parent dirs."""
    db_file = tmp_path / "subdir" / "scout.db"
    engine = get_engine(db_file)
    try:
        init_db(engine)
        assert EXPECTED_TABLES.issubset(_existing_tables(engine))
        assert db_file.exists()
    finally:
        engine.dispose()


def test_get_session_factory_returns_usable_session(memory_engine: Engine) -> None:
    """get_session_factory() must return a sessionmaker that opens sessions."""
    init_db(memory_engine)
    SessionLocal = get_session_factory(memory_engine)
    with SessionLocal() as session:
        result = session.execute(
            text("SELECT name FROM sqlite_master WHERE type='table'")
        ).fetchall()
    table_names = {row[0] for row in result}
    assert EXPECTED_TABLES.issubset(table_names)
