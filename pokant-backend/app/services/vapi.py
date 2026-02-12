"""
Vapi voice AI API client with deployment capabilities.
"""

from datetime import datetime
from typing import Optional

import httpx

from app.config import get_settings


class VapiClient:
    """Async client for the Vapi voice AI API."""

    BASE_URL = "https://api.vapi.ai"

    def __init__(self, api_key: Optional[str] = None):
        settings = get_settings()
        self.api_key = api_key or settings.vapi_test_api_key
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    # ── Call operations ─────────────────────────────────────────────

    async def list_calls(
        self,
        limit: int = 100,
        created_at_gt: Optional[str] = None,
    ) -> list[dict]:
        """Fetch call records from Vapi."""
        params: dict = {"limit": limit}
        if created_at_gt:
            params["createdAtGt"] = created_at_gt

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/call",
                headers=self.headers,
                params=params,
            )
            response.raise_for_status()
            return response.json()

    async def get_call(self, call_id: str) -> dict:
        """Fetch a single call by ID."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/call/{call_id}",
                headers=self.headers,
            )
            response.raise_for_status()
            return response.json()

    async def create_call(self, payload: dict) -> dict:
        """Initiate a new test call via Vapi."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.BASE_URL}/call",
                headers=self.headers,
                json=payload,
            )
            response.raise_for_status()
            return response.json()

    async def get_calls_by_assistant(
        self,
        assistant_id: str,
        created_after: Optional[datetime] = None,
        limit: int = 100,
    ) -> list[dict]:
        """Get calls for a specific assistant (for monitoring A/B tests)."""
        params: dict = {
            "assistantId": assistant_id,
            "limit": limit,
        }
        if created_after:
            params["createdAtGt"] = created_after.isoformat()

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/call",
                headers=self.headers,
                params=params,
            )
            response.raise_for_status()
            return response.json()

    # ── Assistant operations ────────────────────────────────────────

    async def get_assistant(self, assistant_id: str) -> dict:
        """Fetch assistant/bot configuration."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/assistant/{assistant_id}",
                headers=self.headers,
            )
            response.raise_for_status()
            return response.json()

    async def update_assistant(self, assistant_id: str, payload: dict) -> dict:
        """Update assistant configuration (generic)."""
        async with httpx.AsyncClient() as client:
            response = await client.patch(
                f"{self.BASE_URL}/assistant/{assistant_id}",
                headers=self.headers,
                json=payload,
            )
            response.raise_for_status()
            return response.json()

    async def update_assistant_prompt(
        self,
        assistant_id: str,
        new_prompt: str,
    ) -> dict:
        """Update assistant's system prompt (for 100% deployment after A/B win)."""
        return await self.update_assistant(
            assistant_id,
            {
                "model": {
                    "messages": [
                        {"role": "system", "content": new_prompt},
                    ],
                },
            },
        )

    async def create_assistant_variant(
        self,
        base_assistant_id: str,
        variant_prompt: str,
        variant_name: str,
    ) -> dict:
        """
        Create a duplicate assistant for A/B testing.

        Vapi doesn't have native A/B split, so we clone the original
        assistant with a different prompt and route traffic manually.
        """
        base = await self.get_assistant(base_assistant_id)

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.BASE_URL}/assistant",
                headers=self.headers,
                json={
                    "name": f"{base.get('name', 'Bot')} - {variant_name}",
                    "model": {
                        "provider": base.get("model", {}).get("provider", "openai"),
                        "model": base.get("model", {}).get("model", "gpt-4"),
                        "messages": [
                            {"role": "system", "content": variant_prompt},
                        ],
                    },
                    "voice": base.get("voice", {}),
                    "firstMessage": base.get("firstMessage"),
                },
            )
            response.raise_for_status()
            return response.json()

    async def delete_assistant(self, assistant_id: str) -> None:
        """Delete assistant (cleanup after A/B test)."""
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{self.BASE_URL}/assistant/{assistant_id}",
                headers=self.headers,
            )
            response.raise_for_status()
