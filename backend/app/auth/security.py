"""Password hashing + session tokens (stdlib only).

Prototype-grade auth: PBKDF2-HMAC-SHA256 with a per-user random salt for
passwords (never stored in plaintext), and random opaque session tokens.
NOT security-audited / NOT HIPAA-compliant — see docs/user-accounts.md.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets

_ITERATIONS = 200_000


def hash_password(password: str) -> tuple[str, str]:
    """Return (salt_hex, hash_hex) for a new password."""
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, _ITERATIONS
    )
    return salt.hex(), digest.hex()


def verify_password(password: str, salt_hex: str, hash_hex: str) -> bool:
    """Constant-time verify a password against a stored salt+hash."""
    try:
        salt = bytes.fromhex(salt_hex)
    except ValueError:
        return False
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, _ITERATIONS
    )
    return hmac.compare_digest(digest.hex(), hash_hex)


def new_token() -> str:
    return secrets.token_urlsafe(32)
