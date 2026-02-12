import httpx
from typing import Optional

from app.config import get_settings


class RetellClient:
    """Async client for the Retell voice AI API. Stub for future implementation."""

    BASE_URL = "https://api.retellai.com"

    def __init__(self, api_key: Optional[str] = None):
        settings = get_settings()
        self.api_key = api_key or ""
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def list_calls(self, limit: int = 100) -> list[dict]:
        """Fetch call records from Retell - stub."""
        raise NotImplementedError("Retell integration not yet implemented")

    async def get_call(self, call_id: str) -> dict:
        """Fetch a single call - stub."""
        raise NotImplementedError("Retell integration not yet implemented")
