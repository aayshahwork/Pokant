"""
api/middleware/auth.py — API key authentication dependency.

Extracts X-API-Key header, SHA-256 hashes it, validates against the
api_keys table, and returns the associated Account.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.dependencies import get_db
from api.models.account import Account
from api.models.api_key import ApiKey


def _hash_key(raw_key: str) -> str:
    """Return the SHA-256 hex digest of a raw API key."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


async def get_current_account(
    x_api_key: str = Header(..., alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
) -> Account:
    """FastAPI dependency that authenticates via X-API-Key header.

    1. Hash the raw key with SHA-256.
    2. Look up api_keys by key_hash.
    3. Check revoked_at IS NULL and expires_at is valid.
    4. Load the associated Account.
    5. Set current_setting('app.account_id') on the DB connection for RLS.

    Returns the Account on success.
    Raises HTTPException(401) on any failure.
    """
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_code": "UNAUTHORIZED", "message": "Missing API key."},
        )

    key_hash = _hash_key(x_api_key)

    stmt = (
        select(ApiKey)
        .options(selectinload(ApiKey.account))
        .where(ApiKey.key_hash == key_hash)
    )
    result = await db.execute(stmt)
    api_key = result.scalar_one_or_none()

    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_code": "UNAUTHORIZED", "message": "Invalid API key."},
        )

    # Check revoked
    if api_key.revoked_at is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_code": "UNAUTHORIZED", "message": "API key has been revoked."},
        )

    # Check expired
    now = datetime.now(timezone.utc)
    if api_key.expires_at is not None and api_key.expires_at <= now:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_code": "UNAUTHORIZED", "message": "API key has expired."},
        )

    account = api_key.account
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_code": "UNAUTHORIZED", "message": "Account not found."},
        )

    # Set RLS context on the connection
    await db.execute(text(f"SET LOCAL app.account_id = '{account.id}'"))

    return account
