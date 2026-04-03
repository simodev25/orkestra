"""Health check endpoints."""
from fastapi import APIRouter
from app.core.config import get_settings

router = APIRouter()
settings = get_settings()

@router.get("/health")
async def health():
    return {"status": "ok", "service": "orkestra", "version": settings.APP_VERSION}
