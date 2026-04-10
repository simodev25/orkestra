"""Fernet encryption for platform secrets."""
from cryptography.fernet import Fernet
from app.core.config import get_settings

_fernet = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        settings = get_settings()
        key = settings.FERNET_KEY
        if not key:
            # Auto-generate for dev (NOT for production)
            key = Fernet.generate_key().decode()
        _fernet = Fernet(key.encode() if isinstance(key, str) else key)
    return _fernet


def encrypt_value(plaintext: str) -> str:
    """Encrypt a plaintext string, return base64 Fernet token."""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_value(ciphertext: str) -> str:
    """Decrypt a Fernet token, return plaintext string."""
    return _get_fernet().decrypt(ciphertext.encode()).decode()
