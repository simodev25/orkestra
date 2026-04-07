"""Orkestra — Governed multi-agent orchestration platform."""

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.auth import ApiKeyMiddleware
from app.core.config import get_settings
from app.core.logging_config import configure_logging
from app.api.routes import (
    health, requests, cases, agents, mcps, plans, runs,
    control, supervision, approvals, audit, workflows, mcp_catalog, metrics,
    debug_strategy, test_lab,
)
from app.api.routes import settings as settings_routes
from app.api.routes.families import router as families_router
from app.api.routes.skills import router as skills_router
from app.core.database import get_async_session_factory
from app.services import seed_service

settings = get_settings()
logger = logging.getLogger("orkestra")

# Initialize AgentScope tracing at module load (before uvicorn workers fork)
if settings.OTEL_ENDPOINT:
    try:
        from agentscope.tracing import setup_tracing
        setup_tracing(endpoint=settings.OTEL_ENDPOINT)
        logger.info(f"AgentScope OTLP tracing → {settings.OTEL_ENDPOINT}")
    except Exception as exc:
        logger.warning(f"Failed to init tracing: {exc}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    logger.info(f"Orkestra {settings.APP_VERSION} starting")
    try:
        factory = get_async_session_factory()
        async with factory() as db:
            await seed_service.seed_all(db)
    except Exception as exc:
        logger.error(f"Failed to seed families/skills: {exc}")
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
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",")],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-API-Key"],
)
app.add_middleware(ApiKeyMiddleware)

app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(requests.router, prefix="/api/requests", tags=["requests"])
app.include_router(cases.router, prefix="/api/cases", tags=["cases"])
app.include_router(families_router, prefix="/api/families", tags=["families"])
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
app.include_router(metrics.router, prefix="/api", tags=["metrics"])
app.include_router(debug_strategy.router, prefix="/api", tags=["debug-strategy"])
app.include_router(test_lab.router, prefix="/api/test-lab", tags=["test-lab"])
