"""
api/routes/audit.py — Audit log query endpoints.

GET /api/v1/audit                                List audit entries for account
GET /api/v1/audit/{resource_type}/{resource_id}  History for a specific resource
"""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db
from api.middleware.auth import get_current_account
from api.models.account import Account
from api.models.audit_log import AuditLog
from api.schemas.audit import AuditLogEntry, AuditLogListResponse

router = APIRouter(prefix="/api/v1/audit", tags=["Audit"])


@router.get("", response_model=AuditLogListResponse)
async def list_audit_logs(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    action: str | None = Query(default=None),
    since: datetime | None = Query(default=None),
    account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
) -> AuditLogListResponse:
    """List audit log entries for the authenticated account."""
    base = select(AuditLog).where(AuditLog.account_id == account.id)
    count_base = select(func.count(AuditLog.id)).where(AuditLog.account_id == account.id)

    if action:
        base = base.where(AuditLog.action == action)
        count_base = count_base.where(AuditLog.action == action)

    if since:
        base = base.where(AuditLog.created_at >= since)
        count_base = count_base.where(AuditLog.created_at >= since)

    total_result = await db.execute(count_base)
    total = total_result.scalar_one()

    stmt = base.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(stmt)
    rows = result.scalars().all()

    return AuditLogListResponse(
        entries=[AuditLogEntry.model_validate(r) for r in rows],
        total=total,
        has_more=(offset + limit) < total,
    )


@router.get("/{resource_type}/{resource_id}", response_model=AuditLogListResponse)
async def get_resource_history(
    resource_type: str,
    resource_id: uuid.UUID,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
) -> AuditLogListResponse:
    """Get audit history for a specific resource."""
    base = select(AuditLog).where(
        AuditLog.account_id == account.id,
        AuditLog.resource_type == resource_type,
        AuditLog.resource_id == str(resource_id),
    )
    count_base = select(func.count(AuditLog.id)).where(
        AuditLog.account_id == account.id,
        AuditLog.resource_type == resource_type,
        AuditLog.resource_id == str(resource_id),
    )

    total_result = await db.execute(count_base)
    total = total_result.scalar_one()

    stmt = base.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(stmt)
    rows = result.scalars().all()

    return AuditLogListResponse(
        entries=[AuditLogEntry.model_validate(r) for r in rows],
        total=total,
        has_more=(offset + limit) < total,
    )
