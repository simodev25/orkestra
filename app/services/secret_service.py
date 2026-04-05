"""Secret service — read API keys from DB with env fallback."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.secret import PlatformSecret


async def get_secret(db: AsyncSession, key: str, fallback: str = "") -> str:
    """Get a secret value from DB, fall back to provided default."""
    secret = await db.get(PlatformSecret, key)
    if secret and secret.value:
        return secret.value
    return fallback
