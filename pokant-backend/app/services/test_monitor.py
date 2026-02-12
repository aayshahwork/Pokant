"""
Background job to monitor active A/B tests.

Fetches latest results from Vapi, checks if tests are ready
to conclude, and auto-promotes winners after the test window.

Run as cron:
    python -m scripts.monitor_tests
"""

import asyncio
from datetime import datetime

from app.database import SessionLocal
from app.models import ABTest
from app.services.ab_test_manager import ABTestManager
from app.services.statistical_analyzer import StatisticalAnalyzer


async def monitor_active_tests() -> None:
    """Check all running tests, fetch results, auto-promote if ready."""
    db = SessionLocal()
    manager = ABTestManager(db)
    analyzer = StatisticalAnalyzer()

    active_tests = db.query(ABTest).filter(ABTest.status == "running").all()
    print(f"Monitoring {len(active_tests)} active test(s)...")

    for test in active_tests:
        print(f"\nTest {test.id} ({test.name}):")

        try:
            results = await manager.fetch_results(str(test.id))

            ctrl = results["control"]
            var = results["variant"]
            print(f"  Control: {ctrl['calls']} calls, {ctrl['success_rate']}%")
            print(f"  Variant {var.get('letter', '?')}: {var['calls']} calls, {var['success_rate']}%")

            days_running = results["days_running"]

            if days_running < 4:
                print(f"  Still running ({days_running}/4 days)")
                continue

            print(f"  Test window complete ({days_running} days)")

            # Check statistical significance
            significance = analyzer.calculate_significance(
                control_successes=ctrl["successes"],
                control_total=ctrl["calls"],
                variant_successes=var["successes"],
                variant_total=var["calls"],
            )

            print(
                f"  Significance: {significance['confidence_level']}% "
                f"(p={significance['p_value']})"
            )

            if not significance["min_sample_met"]:
                print(f"  {significance.get('message', 'Need more data')}")
                # Extend test by 2 days
                from datetime import timedelta

                test.end_date = test.end_date + timedelta(days=2)
                db.commit()
                print("  Extended test by 2 days")
                continue

            if var["success_rate"] > ctrl["success_rate"] and significance["is_significant"]:
                print("  Variant wins! Auto-promoting...")
                result = await manager.promote_winner(str(test.id))
                print(f"  Promoted: +{result['improvement']}% improvement")
            elif var["success_rate"] <= ctrl["success_rate"]:
                print("  Variant did not outperform control. Marking as failed.")
                test.status = "failed"
                test.completed_at = datetime.utcnow()
                db.commit()
            else:
                print("  Not statistically significant yet. Extending 2 days.")
                from datetime import timedelta

                test.end_date = test.end_date + timedelta(days=2)
                db.commit()

        except Exception as e:
            print(f"  Error: {e}")

    db.close()
    print("\nMonitoring complete.")
