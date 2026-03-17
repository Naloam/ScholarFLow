from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from config.settings import settings


@dataclass(frozen=True)
class AuthIdentity:
    kind: str
    token: str
    user_id: str | None = None
    email: str | None = None


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(raw: str) -> bytes:
    padding = "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode(raw + padding)


def _signature(payload: str, secret: str) -> str:
    signed = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).digest()
    return _b64url_encode(signed)


def extract_api_token(
    authorization: str | None,
    query_token: str | None = None,
) -> str | None:
    if query_token:
        return query_token.strip() or None
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer":
        return None
    return token.strip() or None


def create_user_token(user_id: str, email: str) -> tuple[str, datetime]:
    if not settings.auth_secret:
        raise RuntimeError("AUTH_SECRET is not configured")
    expires_at = datetime.now(UTC) + timedelta(seconds=settings.auth_token_ttl_seconds)
    payload = {
        "sub": user_id,
        "email": email,
        "exp": int(expires_at.timestamp()),
    }
    payload_encoded = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    sig = _signature(payload_encoded, settings.auth_secret)
    return f"sfu1.{payload_encoded}.{sig}", expires_at


def verify_user_token(token: str | None) -> AuthIdentity | None:
    if not token or not settings.auth_secret:
        return None
    prefix, sep, tail = token.partition(".")
    if prefix != "sfu1" or not sep:
        return None
    payload_encoded, sep, provided_sig = tail.partition(".")
    if not sep or not payload_encoded or not provided_sig:
        return None
    expected_sig = _signature(payload_encoded, settings.auth_secret)
    if not hmac.compare_digest(expected_sig, provided_sig):
        return None
    try:
        payload = json.loads(_b64url_decode(payload_encoded).decode("utf-8"))
    except Exception:
        return None
    if int(payload.get("exp", 0)) < int(datetime.now(UTC).timestamp()):
        return None
    user_id = payload.get("sub")
    email = payload.get("email")
    if not user_id or not email:
        return None
    return AuthIdentity(kind="user", token=token, user_id=user_id, email=email)


def authenticate_token(token: str | None) -> AuthIdentity | None:
    if not token:
        return None
    if settings.api_token and token == settings.api_token:
        return AuthIdentity(kind="service", token=token)
    return verify_user_token(token)


def is_request_authorized(token: str | None) -> bool:
    if not settings.api_token and not settings.auth_required:
        return True
    return authenticate_token(token) is not None
