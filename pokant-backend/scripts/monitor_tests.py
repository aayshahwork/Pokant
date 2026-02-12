"""
Cron job script to monitor active A/B tests.

Add to crontab (every 6 hours):
    0 */6 * * * cd /path/to/pokant-backend && python -m scripts.monitor_tests

Usage:
    cd pokant-backend
    python -m scripts.monitor_tests
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.test_monitor import monitor_active_tests

if __name__ == "__main__":
    asyncio.run(monitor_active_tests())
