"""
POST /api/investigate           — run an investigation
GET  /api/investigations        — list past investigations
GET  /api/investigations/{id}   — get results for one investigation
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from scout.cache import ResponseCache
from scout.config import get_config
from scout.db import get_engine, get_session_factory, init_db
from scout.models.db import EdgeRow, Investigation, NodeRow, SourceRun
from scout.models.domain import InputType, Mode
from scout.orchestrator import Orchestrator

router = APIRouter()


# ---------------------------------------------------------------------------
# Dependency injection
# ---------------------------------------------------------------------------


def _get_session() -> Session:
    cfg = get_config()
    engine = get_engine(cfg.db_path)
    init_db(engine)
    factory = get_session_factory(engine)
    with factory() as session:
        yield session


def _get_cache() -> ResponseCache:
    cfg = get_config()
    engine = get_engine(cfg.db_path)
    init_db(engine)
    return ResponseCache(get_session_factory(engine))


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class InvestigateRequest(BaseModel):
    mode: str
    target: str
    target_type: str
    sources: list[str] | None = None


class NodeOut(BaseModel):
    id: str
    type: str
    label: str
    source_name: str
    attrs: dict[str, Any]


class EdgeOut(BaseModel):
    src_id: str
    dst_id: str
    relation: str
    source_name: str


class SourceRunOut(BaseModel):
    source_name: str
    status: str
    cache_hit: bool
    error_message: str | None


class InvestigationOut(BaseModel):
    id: str
    mode: str
    target: str
    target_type: str
    created_at: datetime
    completed_at: datetime | None
    status: str
    note: str | None
    source_runs: list[SourceRunOut] = []
    nodes: list[NodeOut] = []
    edges: list[EdgeOut] = []


class InvestigationSummary(BaseModel):
    id: str
    mode: str
    target: str
    target_type: str
    created_at: datetime
    status: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/api/investigate", response_model=InvestigationOut)
async def investigate(
    req: InvestigateRequest,
    session: Session = Depends(_get_session),
    cache: ResponseCache = Depends(_get_cache),
) -> InvestigationOut:
    try:
        mode = Mode(req.mode)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Unknown mode: {req.mode!r}")

    try:
        input_type = InputType(req.target_type)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Unknown target_type: {req.target_type!r}")

    inv_id = str(uuid.uuid4())
    now = datetime.now(UTC)

    inv = Investigation(
        id=inv_id,
        mode=req.mode,
        target=req.target,
        target_type=req.target_type,
        created_at=now,
        status="running",
    )
    session.add(inv)
    session.commit()

    cfg = get_config()
    api_keys = {
        "haveibeenpwned": cfg.sources.hibp.api_key,
        "virustotal": cfg.sources.virustotal.api_key,
        "abuseipdb": cfg.sources.abuseipdb.api_key,
        "github_user": cfg.sources.github.token,
    }

    orch = Orchestrator(cache=cache)
    async with httpx.AsyncClient(timeout=30.0) as http:
        orch_result = await orch.run(
            mode=mode,
            target=req.target,
            input_type=input_type,
            http=http,
            api_keys=api_keys,
            source_names=req.sources,
        )

    # Persist source runs
    source_run_rows: list[SourceRun] = []
    for run in orch_result.source_runs:
        sr = SourceRun(
            id=str(uuid.uuid4()),
            investigation_id=inv_id,
            source_name=run.source_name,
            started_at=now,
            finished_at=datetime.now(UTC),
            status=run.status,
            error_message=run.error_message,
            cache_hit=run.cache_hit,
        )
        session.add(sr)
        source_run_rows.append(sr)

    # Persist nodes
    node_rows: list[NodeRow] = []
    for node in orch_result.nodes:
        nr = NodeRow(
            id=node.id,
            investigation_id=inv_id,
            type=node.type,
            label=node.label,
            attrs_json=str(node.attrs),
            discovered_by=node.source_name,
        )
        session.add(nr)
        node_rows.append(nr)

    # Persist edges
    edge_rows: list[EdgeRow] = []
    for edge in orch_result.edges:
        er = EdgeRow(
            id=str(uuid.uuid4()),
            investigation_id=inv_id,
            src_node_id=edge.src_id,
            dst_node_id=edge.dst_id,
            relation=edge.relation,
            discovered_by=edge.source_name,
        )
        session.add(er)
        edge_rows.append(er)

    inv.status = "complete"
    inv.completed_at = datetime.now(UTC)
    session.commit()

    return InvestigationOut(
        id=inv_id,
        mode=req.mode,
        target=req.target,
        target_type=req.target_type,
        created_at=now,
        completed_at=inv.completed_at,
        status="complete",
        note=None,
        source_runs=[
            SourceRunOut(
                source_name=r.source_name,
                status=r.status,
                cache_hit=r.cache_hit,
                error_message=r.error_message,
            )
            for r in orch_result.source_runs
        ],
        nodes=[
            NodeOut(id=n.id, type=n.type, label=n.label, source_name=n.source_name, attrs=n.attrs)
            for n in orch_result.nodes
        ],
        edges=[
            EdgeOut(src_id=e.src_id, dst_id=e.dst_id, relation=e.relation, source_name=e.source_name)
            for e in orch_result.edges
        ],
    )


@router.get("/api/investigations", response_model=list[InvestigationSummary])
async def list_investigations(
    session: Session = Depends(_get_session),
    limit: int = 50,
    offset: int = 0,
) -> list[InvestigationSummary]:
    rows = (
        session.query(Investigation)
        .order_by(Investigation.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [
        InvestigationSummary(
            id=r.id,
            mode=r.mode,
            target=r.target,
            target_type=r.target_type,
            created_at=r.created_at,
            status=r.status,
        )
        for r in rows
    ]


@router.get("/api/investigations/{investigation_id}", response_model=InvestigationOut)
async def get_investigation(
    investigation_id: str,
    session: Session = Depends(_get_session),
) -> InvestigationOut:
    inv = session.get(Investigation, investigation_id)
    if inv is None:
        raise HTTPException(status_code=404, detail="Investigation not found")

    source_runs = (
        session.query(SourceRun)
        .filter(SourceRun.investigation_id == investigation_id)
        .all()
    )
    nodes = (
        session.query(NodeRow)
        .filter(NodeRow.investigation_id == investigation_id)
        .all()
    )
    edges = (
        session.query(EdgeRow)
        .filter(EdgeRow.investigation_id == investigation_id)
        .all()
    )

    return InvestigationOut(
        id=inv.id,
        mode=inv.mode,
        target=inv.target,
        target_type=inv.target_type,
        created_at=inv.created_at,
        completed_at=inv.completed_at,
        status=inv.status,
        note=inv.note,
        source_runs=[
            SourceRunOut(
                source_name=r.source_name,
                status=r.status,
                cache_hit=r.cache_hit,
                error_message=r.error_message,
            )
            for r in source_runs
        ],
        nodes=[
            NodeOut(id=n.id, type=n.type, label=n.label, source_name=n.discovered_by, attrs={})
            for n in nodes
        ],
        edges=[
            EdgeOut(
                src_id=e.src_node_id,
                dst_id=e.dst_node_id,
                relation=e.relation,
                source_name=e.discovered_by,
            )
            for e in edges
        ],
    )
