"""
api/routes/alerts.py -- Alert management endpoints.

GET    /api/v1/alerts              List alerts (paginated)
POST   /api/v1/alerts/{alert_id}/ack   Acknowledge an alert
"""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db
from api.middleware.auth import get_current_account
from api.models.account import Account
from api.models.alert import Alert
from api.schemas.alert import AlertListResponse, AlertResponse
from api.schemas.task import ErrorResponse

logger = structlog.get_logger("api.alerts")

router = APIRouter(prefix="/api/v1/alerts", tags=["Alerts"])


@router.get(
    "",
    response_model=AlertListResponse,
)
async def list_alerts(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    acknowledged: bool = Query(default=False),
    account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
) -> AlertListResponse:
    """List alerts for the authenticated account."""
    base = (
        select(Alert)
        .where(Alert.account_id == account.id)
        .where(Alert.acknowledged == acknowledged)
    )

    # Total count
    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    # Paginated results
    stmt = base.order_by(Alert.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(stmt)
    alerts = result.scalars().all()

    return AlertListResponse(
        alerts=[AlertResponse.model_validate(a) for a in alerts],
        total=total,
        has_more=(offset + limit) < total,
    )


@router.post(
    "/{alert_id}/ack",
    status_code=status.HTTP_200_OK,
    responses={404: {"model": ErrorResponse}},
)
async def acknowledge_alert(
    alert_id: uuid.UUID,
    account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Acknowledge an alert."""
    stmt = select(Alert).where(
        Alert.id == alert_id, Alert.account_id == account.id
    )
    result = await db.execute(stmt)
    alert = result.scalar_one_or_none()

    if alert is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "NOT_FOUND", "message": "Alert not found."},
        )

    alert.acknowledged = True
    await db.commit()

    logger.info("alert_acknowledged", alert_id=str(alert_id), account_id=str(account.id))
    return {"id": str(alert_id), "acknowledged": True}
