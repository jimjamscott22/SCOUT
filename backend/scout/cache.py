"""
TTL-aware response cache backed by the SQLite ``response_cache`` table.

Each cache entry is keyed by ``(source_name, request_key)`` where
``request_key`` is a caller-supplied string that uniquely identifies the
request (e.g. ``"email:foo@bar.com"``).  Entries are stored as JSON and
expire at a UTC timestamp set by the caller.

Usage::

    from pathlib import Path
    from scout.db import get_engine, get_session_factory, init_db
    from scout.cache import ResponseCache

    engine = get_engine(Path(":memory:"))
    init_db(engine)
    cache = ResponseCache(get_session_factory(engine))

    cache.set("hibp", "email:foo@bar.com", {"breaches": []}, ttl_seconds=86400)
    data = cache.get("hibp", "email:foo@bar.com")   # dict or None
    cache.evict_expired()
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from scout.models.db import ResponseCache as ResponseCacheRow


def _cache_id(source_name: str, request_key: str) -> str:
    """Return a deterministic primary key for a (source, request_key) pair."""
    digest = hashlib.sha256(f"{source_name}\x00{request_key}".encode()).hexdigest()
    return digest[:32]


class ResponseCache:
    """Synchronous TTL cache stored in the ``response_cache`` SQLite table."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._factory = session_factory

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, source_name: str, request_key: str) -> dict[str, Any] | None:
        """Return the cached response for *(source_name, request_key)* if valid.

        Returns ``None`` if the entry does not exist or has expired.
        Expired entries are deleted on read (lazy eviction).
        """
        with self._factory() as session:
            row = session.get(ResponseCacheRow, _cache_id(source_name, request_key))
            if row is None:
                return None
            if row.expires_at.replace(tzinfo=UTC) <= datetime.now(UTC):
                session.delete(row)
                session.commit()
                return None
            return json.loads(row.response_json)  # type: ignore[no-any-return]

    def set(
        self,
        source_name: str,
        request_key: str,
        data: dict[str, Any],
        *,
        ttl_seconds: float,
    ) -> None:
        """Store *data* under *(source_name, request_key)* with the given TTL.

        If an entry already exists for this key it is replaced.
        """
        now = datetime.now(UTC)
        expires = now + timedelta(seconds=ttl_seconds)
        entry_id = _cache_id(source_name, request_key)

        with self._factory() as session:
            row = session.get(ResponseCacheRow, entry_id)
            if row is None:
                row = ResponseCacheRow(
                    id=entry_id,
                    source_name=source_name,
                    request_key=request_key,
                    response_json=json.dumps(data),
                    fetched_at=now,
                    expires_at=expires,
                )
                session.add(row)
            else:
                row.source_name = source_name
                row.request_key = request_key
                row.response_json = json.dumps(data)
                row.fetched_at = now
                row.expires_at = expires
            session.commit()

    def evict_expired(self) -> int:
        """Delete all expired entries and return the count removed."""
        with self._factory() as session:
            now = datetime.now(UTC)
            rows = (
                session.query(ResponseCacheRow)
                .filter(ResponseCacheRow.expires_at <= now)
                .all()
            )
            for row in rows:
                session.delete(row)
            session.commit()
            return len(rows)
