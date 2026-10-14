"""
Fernet symmetric encryption helpers for storing sensitive values (API keys,
Bearer tokens, passwords) in the database without exposing plaintext.

How it works
------------
- On WRITE: encrypt_value("my-secret") → "enc:gAAA..." (stored in DB)
- On READ : decrypt_value("gAAA...")   → "my-secret"   (used in HTTP request)

The "enc:" prefix is a sentinel added by the *router*, not by these helpers.
These helpers deal only with the raw Fernet token — no prefix logic here.

The ENCRYPTION_KEY must be a valid Fernet key (32 url-safe base64 bytes).
Generate once with:
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""

from cryptography.fernet import Fernet, InvalidToken
from app.core.config import settings


def _get_fernet() -> Fernet:
    """Build a Fernet instance from the configured key.

    Called lazily (not at import time) so the app can still start even if
    ENCRYPTION_KEY is not set yet — but any call to encrypt/decrypt will
    raise a clear error if the key is missing or invalid.
    """
    key = settings.ENCRYPTION_KEY
    if not key:
        raise RuntimeError(
            "ENCRYPTION_KEY is not set in .env. "
            "Generate one with: "
            "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    return Fernet(key.encode())


def encrypt_value(plaintext: str) -> str:
    """Encrypt a plaintext string and return a base64 Fernet token."""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_value(token: str) -> str:
    """Decrypt a Fernet token back to plaintext.

    Raises:
        cryptography.fernet.InvalidToken  if the token is corrupted or the
                                          wrong key is used.
    """
    try:
        return _get_fernet().decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise ValueError(
            "Failed to decrypt a stored credential. "
            "The ENCRYPTION_KEY may have changed since the value was stored."
        ) from exc
