"""
api/schemas/alert.py -- Pydantic v2 request/response models for the Alerts API.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class AlertResponse(BaseModel):
    """Representation of a single alert."""

    id: uuid.UUID
    alert_type: str
    message: str
    task_id: uuid.UUID | None = None
    acknowledged: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


class AlertListResponse(BaseModel):
    """Paginated list of alerts."""

    alerts: list[AlertResponse]
    total: int
    has_more: bool
