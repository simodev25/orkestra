"""Orkestra — Governed multi-agent orchestration platform."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.api.routes import health, requests, cases, agents, mcps

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    import logging
    logger = logging.getLogger("orkestra")
    logger.info(f"Orkestra {settings.APP_VERSION} starting")
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
app.include_router(agents.router, prefix="/api/agents", tags=["agents"])
app.include_router(mcps.router, prefix="/api/mcps", tags=["mcps"])
