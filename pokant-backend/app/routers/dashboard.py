import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Call, Pattern
from app.schemas import DashboardStats

router = APIRouter()


@router.get("/dashboard/{customer_id}", response_model=DashboardStats)
async def get_dashboard(customer_id: str, db: Session = Depends(get_db)):
    """Get dashboard data - queries real data, falls back to mock."""
    try:
        cid = uuid.UUID(customer_id)
    except ValueError:
        return _mock_dashboard()

    # Count total calls
    total_calls = (
        db.query(func.count(Call.id))
        .filter(Call.customer_id == cid)
        .scalar()
    ) or 0

    if total_calls == 0:
        return _mock_dashboard()

    # Success rate
    successful = (
        db.query(func.count(Call.id))
        .filter(Call.customer_id == cid, Call.outcome == "success")
        .scalar()
    ) or 0
    success_rate = round((successful / total_calls) * 100, 1) if total_calls else 0.0

    # Average duration
    avg_duration = (
        db.query(func.avg(Call.duration_seconds))
        .filter(Call.customer_id == cid)
        .scalar()
    ) or 0.0

    # Failure categories
    failure_rows = (
        db.query(Call.failure_category, func.count(Call.id))
        .filter(Call.customer_id == cid, Call.failure_category.isnot(None))
        .group_by(Call.failure_category)
        .all()
    )
    failure_categories = {cat: count for cat, count in failure_rows}

    # Recent calls
    recent = (
        db.query(Call)
        .filter(Call.customer_id == cid)
        .order_by(Call.created_at.desc())
        .limit(10)
        .all()
    )
    recent_calls = [
        {
            "id": str(c.id),
            "outcome": c.outcome,
            "duration": c.duration_seconds,
            "sentiment": c.sentiment_score,
            "failure_category": c.failure_category,
            "timestamp": c.created_at.isoformat() if c.created_at else None,
        }
        for c in recent
    ]

    # Trend data (daily aggregates for last 7 days)
    success_case = case((Call.outcome == "success", 1), else_=0)
    trend_data = (
        db.query(
            func.date(Call.created_at).label("date"),
            func.count(Call.id).label("total"),
            func.sum(success_case).label("successes"),
        )
        .filter(Call.customer_id == cid)
        .group_by(func.date(Call.created_at))
        .order_by(func.date(Call.created_at).desc())
        .limit(7)
        .all()
    )

    trend = []
    for row in trend_data:
        day_total = row.total or 1
        day_success = row.successes or 0
        trend.append({
            "date": str(row.date),
            "success_rate": round((day_success / day_total) * 100, 1),
            "total_calls": day_total,
        })

    return DashboardStats(
        total_calls=total_calls,
        success_rate=success_rate,
        avg_duration=round(float(avg_duration), 1),
        failure_categories=failure_categories,
        recent_calls=recent_calls,
        trend_data=list(reversed(trend)),
    )


def _mock_dashboard() -> DashboardStats:
    """Fallback mock data when no real data exists."""
    return DashboardStats(
        total_calls=1247,
        success_rate=73.2,
        avg_duration=184.5,
        failure_categories={
            "Customer Requests Escalation": 42,
            "Complex Inquiry": 28,
            "Account Verification": 19,
            "Unclear Issue Description": 15,
        },
        recent_calls=[
            {
                "id": "call-001",
                "outcome": "success",
                "duration": 195.3,
                "sentiment": 0.82,
                "timestamp": "2024-01-15T10:30:00Z",
            },
            {
                "id": "call-002",
                "outcome": "failure",
                "duration": 312.7,
                "sentiment": 0.31,
                "failure_category": "Customer Requests Escalation",
                "timestamp": "2024-01-15T10:45:00Z",
            },
        ],
        trend_data=[
            {"date": "2024-01-09", "success_rate": 71.5, "total_calls": 180},
            {"date": "2024-01-10", "success_rate": 72.0, "total_calls": 175},
            {"date": "2024-01-11", "success_rate": 70.8, "total_calls": 192},
            {"date": "2024-01-12", "success_rate": 74.1, "total_calls": 168},
            {"date": "2024-01-13", "success_rate": 73.5, "total_calls": 185},
            {"date": "2024-01-14", "success_rate": 72.9, "total_calls": 170},
            {"date": "2024-01-15", "success_rate": 73.2, "total_calls": 177},
        ],
    )
