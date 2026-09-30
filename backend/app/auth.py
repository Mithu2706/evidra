"""Minimal, dependency-free authentication.

Passwords are hashed with PBKDF2-SHA256. Session tokens are HMAC-signed
`user_id.expiry.signature` strings. This is adequate for an MVP/pilot; a
production deployment would sit behind the organization's SSO.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time

from .config import get_settings

_ITERATIONS = 200_000


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITERATIONS)
    return f"pbkdf2${_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iterations, salt_hex, digest_hex = stored.split("$")
    except ValueError:
        return False
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations)
    )
    return hmac.compare_digest(digest.hex(), digest_hex)


def _sign(payload: str) -> str:
    key = get_settings().secret_key.encode()
    sig = hmac.new(key, payload.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(sig).decode().rstrip("=")


def issue_token(user_id: int) -> str:
    expiry = int(time.time()) + get_settings().token_ttl_hours * 3600
    payload = f"{user_id}.{expiry}"
    return f"{payload}.{_sign(payload)}"


def read_token(token: str) -> int | None:
    try:
        user_id, expiry, signature = token.split(".")
    except ValueError:
        return None
    if not hmac.compare_digest(_sign(f"{user_id}.{expiry}"), signature):
        return None
    if int(expiry) < time.time():
        return None
    return int(user_id)
