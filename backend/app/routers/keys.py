from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import generate_key, require_api_key
from app.database import get_db
from app.models import ApiKey

router = APIRouter(prefix="/api/v1/keys", tags=["keys"])


class CreateKeyBody(BaseModel):
    name: str


@router.post("", status_code=201)
async def create_key(body: CreateKeyBody, db: AsyncSession = Depends(get_db)) -> dict:
    raw, hashed = generate_key()
    key = ApiKey(name=body.name, key_hash=hashed, key_prefix=raw[:10])
    db.add(key)
    await db.commit()
    await db.refresh(key)
    return {
        "id": key.id,
        "name": key.name,
        "key": raw,
        "prefix": key.key_prefix,
        "created_at": key.created_at.isoformat(),
        "note": "Store this key securely. It will not be shown again.",
    }


@router.get("")
async def list_keys(api_key: ApiKey = Depends(require_api_key), db: AsyncSession = Depends(get_db)) -> dict:
    result = await db.execute(select(ApiKey).where(ApiKey.is_active.is_(True)))
    keys = result.scalars().all()
    return {"keys": [{"id": k.id, "name": k.name, "prefix": k.key_prefix, "created_at": k.created_at.isoformat()} for k in keys]}


@router.delete("/{key_id}", status_code=204)
async def revoke_key(key_id: int, api_key: ApiKey = Depends(require_api_key), db: AsyncSession = Depends(get_db)) -> None:
    result = await db.execute(select(ApiKey).where(ApiKey.id == key_id))
    key = result.scalar_one_or_none()
    if key:
        key.is_active = False
        await db.commit()
