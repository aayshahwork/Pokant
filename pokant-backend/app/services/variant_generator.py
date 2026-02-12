"""
Generate prompt variants for a failure pattern using GPT-4.
"""

from __future__ import annotations

import json
from typing import List, Dict

from openai import AsyncOpenAI
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Pattern, Call, CallAttribute


class VariantGenerator:
    """
    Week 3: GPT-4o based variant generator.

    Given a failure Pattern ID, this service:
    - Fetches the pattern and a handful of example failed calls
    - Asks GPT-4o to propose 5 distinct prompt variants
    - Normalizes the response into a list[dict]
    """

    def __init__(self, db: Session):
        self.db = db
        settings = get_settings()
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = "gpt-4o"

    async def generate_variants(self, pattern_id: str) -> List[Dict]:
        """
        Generate 5 prompt variants for a failure pattern.

        Args:
            pattern_id: Pattern UUID (string)

        Returns:
            List of up to 5 variant dicts with:
            - letter
            - name
            - approach
            - prompt_text
        """

        pattern = (
            self.db.query(Pattern)
            .filter(Pattern.id == pattern_id)
            .first()
        )

        if not pattern:
            raise ValueError(f"Pattern {pattern_id} not found")

        examples = self._get_failure_examples(pattern_id, limit=10)

        system_prompt = """You are an expert at optimizing conversational AI prompts. 
Your goal is to fix specific failure patterns in voice bots by generating improved prompts.

Generate 5 different prompt variants that each take a unique approach to solving the problem.
Each variant should be:
- Specific and actionable
- Under 100 words
- Focused on handling the failure scenario
- Written as instructions the bot can follow

Return ONLY valid JSON (no markdown)."""

        user_prompt = f"""Failure Pattern: {pattern.name}

Description: {pattern.description}
Root Cause: {pattern.root_cause}
Frequency: {pattern.frequency} failures
Current success rate: ~65%

Example Failed Conversations:
{self._format_examples(examples)}

Generate 5 prompt variants that would prevent these failures. Each should take a different approach:

1. **Standard Acknowledgment** - Simple, clear confirmation
2. **Explicit Confirmation** - Repeat back what customer said and confirm
3. **Empathetic Response** - Acknowledge emotion, then handle request
4. **Clarifying Question** - Ask question to understand intent
5. **Summary Confirmation** - Summarize the full request before proceeding

Return JSON array:
[
  {{
    "letter": "A",
    "name": "Standard Acknowledgment",
    "approach": "Brief description of approach",
    "prompt_text": "The actual prompt instructions for the bot"
  }},
  ...
]"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.8,
                max_tokens=2000,
            )

            content = response.choices[0].message.content or ""

            # Strip markdown fences if model decides to add them anyway
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            variants = json.loads(content)

            # Ensure we have a list
            if isinstance(variants, dict):
                variants = [variants]

            letters = ["A", "B", "C", "D", "E"]
            normalized: List[Dict] = []

            for i, variant in enumerate(variants[:5]):
                v = dict(variant)
                # Normalize required keys
                v.setdefault("letter", letters[i] if i < len(letters) else letters[-1])
                v.setdefault("name", f"Variant {v['letter']}")
                v.setdefault("approach", "")
                v.setdefault("prompt_text", "")
                normalized.append(v)

            # Always return exactly 5 entries if possible
            if len(normalized) < 5:
                # Top up with fallbacks
                fallback = self._get_fallback_variants(pattern)
                needed = 5 - len(normalized)
                normalized.extend(fallback[:needed])

            return normalized[:5]

        except Exception as e:  # noqa: BLE001
            print(f"Error generating variants: {e}")
            return self._get_fallback_variants(pattern)

    def _get_failure_examples(self, pattern_id: str, limit: int = 10) -> List[Dict]:
        """
        Get example failed calls for this pattern.

        Currently:
        - Fetches calls whose CallAttribute.failure_pattern matches the pattern name.
        - Truncates transcripts for prompt brevity.
        """

        pattern = (
            self.db.query(Pattern)
            .filter(Pattern.id == pattern_id)
            .first()
        )
        if not pattern:
            return []

        key = (pattern.name or "").lower().replace(" ", "_")

        examples = (
            self.db.query(Call, CallAttribute)
            .join(CallAttribute, Call.id == CallAttribute.call_id)
            .filter(CallAttribute.failure_pattern == key)
            .limit(limit)
            .all()
        )

        return [
            {
                "transcript": (call.transcript or "")[:300],
                "accent_strength": attrs.accent_strength,
                "corrections": attrs.correction_attempts,
                "emotional_markers": attrs.emotional_markers or [],
            }
            for call, attrs in examples
        ]

    def _format_examples(self, examples: List[Dict]) -> str:
        """Nicely format examples for inclusion in the GPT prompt."""

        formatted: List[str] = []
        for i, ex in enumerate(examples[:5], 1):
            transcript = ex.get("transcript", "")
            accent = ex.get("accent_strength", "?")
            corrections = ex.get("corrections", 0)
            emotions = ", ".join(ex.get("emotional_markers", [])) or "neutral"

            formatted.append(
                f"""
Example {i}:
{transcript}
[Accent: {accent}/5, Corrections: {corrections}, Emotion: {emotions}]
""".rstrip()
            )

        return "\n\n".join(formatted)

    def _get_fallback_variants(self, pattern: Pattern) -> List[Dict]:
        """
        Fallback variants if GPT-4 fails.

        These are generic but follow the same schema as the real variants.
        """

        return [
            {
                "letter": "A",
                "name": "Standard Acknowledgment",
                "approach": "Simple confirmation of the customer's request.",
                "prompt_text": "Acknowledge the customer's request in clear language, then confirm you are taking the requested action.",
            },
            {
                "letter": "B",
                "name": "Explicit Confirmation",
                "approach": "Repeat back the change and ask for confirmation.",
                "prompt_text": "Restate the customer's new request in your own words and explicitly ask the customer to confirm before proceeding.",
            },
            {
                "letter": "C",
                "name": "Empathetic Response",
                "approach": "Acknowledge emotion, then handle the change.",
                "prompt_text": "Acknowledge how the customer feels about changing their mind, then clearly explain what you will update for them.",
            },
            {
                "letter": "D",
                "name": "Clarifying Question",
                "approach": "Ask a focused question to disambiguate the new request.",
                "prompt_text": "Ask one clear question to clarify exactly what the customer wants now, then repeat the clarified request back before proceeding.",
            },
            {
                "letter": "E",
                "name": "Summary Confirmation",
                "approach": "Summarize the full request before proceeding.",
                "prompt_text": "Summarize the customer's situation and new request in one sentence, then ask for a quick yes/no confirmation before taking action.",
            },
        ]

