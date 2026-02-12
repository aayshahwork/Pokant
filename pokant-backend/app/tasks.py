"""
Celery background tasks.
"""

import asyncio

from app.celery_app import celery_app
from app.services.test_monitor import monitor_active_tests


def _run_analyze_customer(customer_id: str, limit: int = 1000) -> dict:
    """Run async analyze_customer in sync context."""
    from scripts.analyze_customer import analyze_customer

    try:
        asyncio.run(analyze_customer(customer_id, limit))
        return {"status": "success", "customer_id": customer_id}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@celery_app.task(name="analyze_customer")
def analyze_customer_task(customer_id: str, limit: int = 1000):
    """
    Run full customer analysis pipeline in background.

    Usage:
        from app.tasks import analyze_customer_task
        analyze_customer_task.delay(customer_id)
    """
    return _run_analyze_customer(customer_id, limit)


@celery_app.task(name="monitor_tests")
def monitor_tests_task():
    """
    Check all active A/B tests and update results.

    Run via beat:
        celery -A app.celery_app beat --loglevel=info
    """
    try:
        asyncio.run(monitor_active_tests())
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


# Schedule periodic tasks
celery_app.conf.beat_schedule = {
    "monitor-tests-every-hour": {
        "task": "monitor_tests",
        "schedule": 3600.0,  # Every hour
    },
}
