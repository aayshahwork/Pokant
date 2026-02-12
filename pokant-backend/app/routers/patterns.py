import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Pattern
from app.schemas import PatternResponse

router = APIRouter()


@router.get("/patterns/{customer_id}", response_model=list[PatternResponse])
async def get_patterns(customer_id: str, db: Session = Depends(get_db)):
    """Get failure patterns - queries real data, falls back to mock."""
    try:
        cid = uuid.UUID(customer_id)
    except ValueError:
        return _mock_patterns()

    patterns = (
        db.query(Pattern)
        .filter(Pattern.customer_id == cid)
        .order_by(Pattern.frequency.desc())
        .all()
    )

    if not patterns:
        return _mock_patterns()

    return patterns


def _mock_patterns() -> list[PatternResponse]:
    """Fallback mock data when no real patterns exist."""
    return [
        PatternResponse(
            id=uuid.uuid4(),
            name="Escalation Request Handling",
            description="Bot fails to properly route customers requesting supervisor escalation",
            failure_type="Customer Requests Escalation",
            frequency=42,
            severity="critical",
            revenue_impact_monthly=840.0,
            root_cause="Bot doesn't recognize correction attempts",
            suggested_fix="Add escalation detection with immediate warm transfer to live agent",
            created_at=datetime.utcnow(),
        ),
        PatternResponse(
            id=uuid.uuid4(),
            name="Complex Multi-Issue Inquiry",
            description="Bot loses context when customer raises multiple issues in one call",
            failure_type="Complex Inquiry",
            frequency=28,
            severity="high",
            revenue_impact_monthly=560.0,
            root_cause="Bot can't handle multi-step workflows",
            suggested_fix="Implement issue queuing - acknowledge all issues, resolve sequentially",
            created_at=datetime.utcnow(),
        ),
        PatternResponse(
            id=uuid.uuid4(),
            name="Account Verification Loop",
            description="Bot repeatedly asks for verification details already provided",
            failure_type="Account Verification",
            frequency=19,
            severity="medium",
            revenue_impact_monthly=380.0,
            root_cause="Bot loses context mid-conversation",
            suggested_fix="Cache verified identity data within the session context",
            created_at=datetime.utcnow(),
        ),
    ]
