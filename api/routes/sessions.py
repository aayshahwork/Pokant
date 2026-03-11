"""
api/routes/sessions.py — Session management endpoints.

POST   /api/v1/sessions          Create or refresh a session
GET    /api/v1/sessions/{id}     Get session metadata (no cookies)
DELETE /api/v1/sessions/{id}     Delete session
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, HttpUrl
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db
from api.middleware.auth import get_current_account
from api.models.account import Account
from api.models.session import Session
from api.services.audit_logger import SESSION_DELETED, AuditLogger

logger = structlog.get_logger("api.sessions")

router = APIRouter(prefix="/api/v1/sessions", tags=["Sessions"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class SessionCreateRequest(BaseModel):
    url: HttpUrl
    cookies_encrypted: bytes | None = None


class SessionResponse(BaseModel):
    session_id: uuid.UUID
    origin_domain: str
    auth_state: str | None
    last_used_at: datetime | None
    expires_at: datetime | None
    created_at: datetime | None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# POST /api/v1/sessions
# ---------------------------------------------------------------------------

@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=SessionResponse,
)
async def create_session(
    body: SessionCreateRequest,
    account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
) -> SessionResponse:
    """Create or refresh a browser session for a URL."""
    from urllib.parse import urlparse

    domain = urlparse(str(body.url)).hostname or str(body.url)

    # Check for existing session on this domain
    stmt = select(Session).where(
        Session.account_id == account.id,
        Session.origin_domain == domain,
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    now = datetime.now(timezone.utc)

    if existing:
        existing.auth_state = "active"
        existing.last_used_at = now
        if body.cookies_encrypted:
            existing.cookies_encrypted = body.cookies_encrypted
        await db.commit()
        await db.refresh(existing)
        session = existing
    else:
        session = Session(
            id=uuid.uuid4(),
            account_id=account.id,
            origin_domain=domain,
            cookies_encrypted=body.cookies_encrypted or b"",
            auth_state="active",
            last_used_at=now,
            created_at=now,
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)

    return SessionResponse(
        session_id=session.id,
        origin_domain=session.origin_domain,
        auth_state=session.auth_state,
        last_used_at=session.last_used_at,
        expires_at=session.expires_at,
        created_at=session.created_at,
    )


# ---------------------------------------------------------------------------
# GET /api/v1/sessions/{session_id}
# ---------------------------------------------------------------------------

@router.get(
    "/{session_id}",
    response_model=SessionResponse,
)
async def get_session(
    session_id: uuid.UUID,
    account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
) -> SessionResponse:
    """Return session metadata (never cookies)."""
    stmt = select(Session).where(
        Session.id == session_id,
        Session.account_id == account.id,
    )
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "NOT_FOUND", "message": "Session not found."},
        )

    return SessionResponse(
        session_id=session.id,
        origin_domain=session.origin_domain,
        auth_state=session.auth_state,
        last_used_at=session.last_used_at,
        expires_at=session.expires_at,
        created_at=session.created_at,
    )


# ---------------------------------------------------------------------------
# DELETE /api/v1/sessions/{session_id}
# ---------------------------------------------------------------------------

@router.delete(
    "/{session_id}",
    status_code=status.HTTP_200_OK,
)
async def delete_session(
    session_id: uuid.UUID,
    request: Request,
    account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Delete a session."""
    stmt = select(Session).where(
        Session.id == session_id,
        Session.account_id == account.id,
    )
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "NOT_FOUND", "message": "Session not found."},
        )

    await db.delete(session)
    await AuditLogger(db).log(
        account_id=account.id,
        actor_type="user",
        actor_id=str(account.id),
        action=SESSION_DELETED,
        resource_type="session",
        resource_id=str(session_id),
        metadata={"origin_domain": session.origin_domain},
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()

    logger.info("session_deleted", session_id=str(session_id), account_id=str(account.id))
    return {"session_id": str(session_id), "message": "Session deleted."}
