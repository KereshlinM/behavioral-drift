"""API key authentication."""

import hashlib
import secrets

from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import ApiKey

_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def generate_key() -> tuple[str, str]:
    """Return (raw_key, key_hash). raw_key is shown once, never stored."""
    raw = "dk_" + secrets.token_urlsafe(32)
    return raw, hash_key(raw)


async def require_api_key(
    raw_key: str | None = Security(_header),
    db: AsyncSession = Depends(get_db),
) -> ApiKey:
    if not raw_key:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header.")
    result = await db.execute(
        select(ApiKey).where(ApiKey.key_hash == hash_key(raw_key), ApiKey.is_active.is_(True))
    )
    key = result.scalar_one_or_none()
    if not key:
        raise HTTPException(status_code=401, detail="Invalid or inactive API key.")
    return key
