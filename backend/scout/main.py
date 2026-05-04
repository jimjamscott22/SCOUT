"""FastAPI application entry point."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import scout.sources.footprint  # noqa: F401 — registers footprint source plugins
import scout.sources.threat  # noqa: F401 — registers threat source plugins
from scout.api.routes_health import router as health_router
from scout.api.routes_investigate import router as investigate_router
from scout.api.routes_sources import router as sources_router

app = FastAPI(title="SCOUT", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(sources_router)
app.include_router(investigate_router)
