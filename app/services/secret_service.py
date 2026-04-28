"""Secret service — read API keys from DB with env fallback."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import decrypt_value
from app.models.secret import PlatformSecret


async def get_secret(db: AsyncSession, key: str, fallback: str = "") -> str:
    """Get a secret value from DB (decrypted), fall back to provided default."""
    secret = await db.get(PlatformSecret, key)
    if secret and secret.value:
        try:
            return decrypt_value(secret.value)
        except Exception:
            # Value might be stored unencrypted (legacy); return as-is
            return secret.value
    return fallback
