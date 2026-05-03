"""
SQLAlchemy ORM models for SCOUT.

These models use the SQLAlchemy 2.x `mapped_column` style with `DeclarativeBase`.
They are used for type-safe ORM queries against the SQLite database whose schema
is created by `scout.db.init_db()`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Investigation(Base):
    __tablename__ = "investigations"

    id: Mapped[str] = mapped_column(primary_key=True)
    mode: Mapped[str]
    target: Mapped[str]
    target_type: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(default=None)
    status: Mapped[str] = mapped_column(default="running")
    note: Mapped[Optional[str]] = mapped_column(default=None)


class SourceRun(Base):
    __tablename__ = "source_runs"

    id: Mapped[str] = mapped_column(primary_key=True)
    investigation_id: Mapped[str] = mapped_column(
        ForeignKey("investigations.id", ondelete="CASCADE")
    )
    source_name: Mapped[str]
    started_at: Mapped[datetime]
    finished_at: Mapped[Optional[datetime]] = mapped_column(default=None)
    status: Mapped[str]
    error_message: Mapped[Optional[str]] = mapped_column(default=None)
    cache_hit: Mapped[bool] = mapped_column(default=False)


class NodeRow(Base):
    __tablename__ = "nodes"

    id: Mapped[str] = mapped_column(primary_key=True)
    investigation_id: Mapped[str] = mapped_column(
        ForeignKey("investigations.id", ondelete="CASCADE"),
        primary_key=True,
    )
    type: Mapped[str]
    label: Mapped[str]
    attrs_json: Mapped[str] = mapped_column(default="{}")
    discovered_by: Mapped[str]


class EdgeRow(Base):
    __tablename__ = "edges"

    __table_args__ = (
        UniqueConstraint(
            "investigation_id",
            "src_node_id",
            "dst_node_id",
            "relation",
            name="uq_edges_inv_src_dst_rel",
        ),
    )

    id: Mapped[str] = mapped_column(primary_key=True)
    investigation_id: Mapped[str] = mapped_column(
        ForeignKey("investigations.id", ondelete="CASCADE")
    )
    src_node_id: Mapped[str]
    dst_node_id: Mapped[str]
    relation: Mapped[str]
    discovered_by: Mapped[str]


class ResponseCache(Base):
    __tablename__ = "response_cache"

    id: Mapped[str] = mapped_column(primary_key=True)
    source_name: Mapped[str]
    request_key: Mapped[str]
    response_json: Mapped[str]
    fetched_at: Mapped[datetime]
    expires_at: Mapped[datetime]
