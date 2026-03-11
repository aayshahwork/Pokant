"""
api/schemas/audit.py — Pydantic v2 request/response models for the Audit Log API.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AuditLogEntry(BaseModel):
    """A single audit log entry."""

    id: uuid.UUID
    actor_type: str
    actor_id: str
    action: str
    resource_type: str
    resource_id: str
    metadata: dict[str, Any] | None = Field(default=None, validation_alias="metadata_")
    ip_address: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogListResponse(BaseModel):
    """Paginated list of audit log entries."""

    entries: list[AuditLogEntry]
    total: int
    has_more: bool
