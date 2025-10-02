from __future__ import annotations
import base64
import hashlib
import json
from typing import Any, Dict, Optional

from cryptography.fernet import Fernet, InvalidToken

from .config import settings


def _derive_fernet_key(secret: str) -> bytes:
    """Derive a urlsafe base64-encoded 32-byte key from an arbitrary secret string."""
    # Use SHA256 of the secret, then urlsafe_b64encode to get a Fernet-compatible key
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def _get_cipher() -> Fernet:
    key = _derive_fernet_key(settings.SECRET_KEY)
    return Fernet(key)


def encrypt_str(plaintext: str) -> str:
    """Encrypt a string into a Fernet token (str)."""
    token = _get_cipher().encrypt(plaintext.encode("utf-8"))
    return token.decode("utf-8")


def decrypt_str(token: str) -> str:
    """Decrypt a Fernet token (str) back to a plaintext string.

    Raises InvalidToken if the token cannot be decrypted.
    """
    try:
        plaintext = _get_cipher().decrypt(token.encode("utf-8"))
        return plaintext.decode("utf-8")
    except InvalidToken:
        raise


def encrypt_json(data: Dict[str, Any]) -> str:
    """Encrypt a JSON-serializable dict as a string token."""
    return encrypt_str(json.dumps(data))


def decrypt_json(token: str) -> Dict[str, Any]:
    """Decrypt a token to a dict.

    Returns an empty dict if token is falsy. Raises InvalidToken if invalid.
    """
    if not token:
        return {}
    return json.loads(decrypt_str(token))
