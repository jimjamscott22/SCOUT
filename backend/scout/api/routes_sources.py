"""GET /api/sources — list registered source plugins."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from scout.config import get_config
from scout.models.domain import InputType, Mode
from scout.sources.base import get_sources

router = APIRouter()


class SourceInfo(BaseModel):
    name: str
    modes: list[str]
    accepts: list[str]
    auth_required: bool
    configured: bool


@router.get("/api/sources", response_model=list[SourceInfo])
async def list_sources(mode: str | None = None) -> list[SourceInfo]:
    if mode is not None:
        try:
            mode_enum: Mode | None = Mode(mode)
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Unknown mode: {mode!r}")
    else:
        mode_enum = None
    sources = get_sources(mode=mode_enum)
    cfg = get_config()
    sources_dict = cfg.sources.model_dump()

    results: list[SourceInfo] = []
    for src in sources:
        entry = sources_dict.get(src.name, {})
        api_key = entry.get("api_key") or entry.get("token") or ""
        configured = (not src.auth_required) or bool(api_key)
        results.append(
            SourceInfo(
                name=src.name,
                modes=sorted(src.modes),
                accepts=sorted(src.accepts),
                auth_required=src.auth_required,
                configured=configured,
            )
        )
    return results
