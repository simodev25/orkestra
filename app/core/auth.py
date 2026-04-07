"""API Key authentication for Orkestra."""
from fastapi import HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import get_settings


class ApiKeyMiddleware(BaseHTTPMiddleware):
    """Middleware that enforces API key authentication on non-public paths."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        settings = get_settings()

        if not settings.AUTH_ENABLED:
            return await call_next(request)

        # Allow CORS preflight
        if request.method == "OPTIONS":
            return await call_next(request)

        # Check if path is public
        public_paths = [p.strip() for p in settings.PUBLIC_PATHS.split(",")]
        path = request.url.path
        if any(path.startswith(pp) for pp in public_paths):
            return await call_next(request)

        # Validate API key
        api_key = request.headers.get("X-API-Key")
        valid_keys = [k.strip() for k in settings.API_KEYS.split(",")]

        if not api_key or api_key not in valid_keys:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing or invalid API key",
            )

        return await call_next(request)
