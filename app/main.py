"""Orkestra — Governed multi-agent orchestration platform."""

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.api.routes import (
    health, requests, cases, agents, mcps, plans, runs,
    control, supervision, approvals, audit, workflows, mcp_catalog,
)
from app.api.routes import settings as settings_routes
from app.api.routes.skills import router as skills_router
from app.services import skill_registry_service

settings = get_settings()
logger = logging.getLogger("orkestra")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Orkestra {settings.APP_VERSION} starting")
    try:
        skill_registry_service.load_skills()
    except Exception as exc:
        logger.error(f"Failed to load skills.seed.json: {exc}")
        raise
    yield
    logger.info("Orkestra shutting down")


app = FastAPI(
    title="Orkestra API",
    description="Governed multi-agent orchestration platform",
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(requests.router, prefix="/api/requests", tags=["requests"])
app.include_router(cases.router, prefix="/api/cases", tags=["cases"])
app.include_router(skills_router, prefix="/api/skills", tags=["skills"])
app.include_router(agents.router, prefix="/api/agents", tags=["agents"])
app.include_router(mcps.router, prefix="/api/mcps", tags=["mcps"])
app.include_router(mcp_catalog.router, prefix="/api/mcp-catalog", tags=["mcp-catalog"])
app.include_router(plans.router, prefix="/api", tags=["plans"])
app.include_router(runs.router, prefix="/api", tags=["runs"])
app.include_router(control.router, prefix="/api", tags=["control"])
app.include_router(supervision.router, prefix="/api", tags=["supervision"])
app.include_router(approvals.router, prefix="/api/approvals", tags=["approvals"])
app.include_router(audit.router, prefix="/api", tags=["audit"])
app.include_router(workflows.router, prefix="/api/workflow-definitions", tags=["workflows"])
app.include_router(settings_routes.router, prefix="/api/settings", tags=["settings"])
