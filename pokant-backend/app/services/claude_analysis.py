"""
Claude-powered transcript analysis.

Uses Claude 3.5 Sonnet to analyze call transcripts and extract
15 structured attributes for pattern detection.
"""

import json
from typing import Optional

import anthropic

from app.config import get_settings


class ClaudeAnalyzer:
    def __init__(self, api_key: Optional[str] = None):
        settings = get_settings()
        self.client = anthropic.AsyncAnthropic(
            api_key=api_key or settings.claude_api_key,
        )
        self.model = "claude-sonnet-4-5-20250929"

    async def analyze_transcript(self, transcript: str, outcome: str) -> dict:
        """
        Analyze a single call transcript and extract 15 attributes.

        Args:
            transcript: Full conversation text.
            outcome: 'success', 'failed', or 'abandoned'.

        Returns:
            Dictionary with 15 extracted attributes.
        """
        prompt = f"""Analyze this voice bot call transcript and extract these attributes.

Call outcome: {outcome}

Transcript:
{transcript}

Extract the following (return ONLY valid JSON, no markdown):

{{
  "accent_strength": <1-5, where 5=very strong accent detected>,
  "correction_attempts": <number of times customer tries to correct bot>,
  "emotional_markers": [<array of: "frustrated", "confused", "angry", "neutral", "happy">],
  "disfluency_count": <count of um, uh, pauses, restarts>,
  "background_noise": "<none|low|medium|high - infer from transcript mentions>",
  "context_type": "<appointment|inquiry|complaint|modification|cancellation>",
  "failure_pattern": "<customer_changes_mind|complex_scheduling|unclear_availability|bot_confusion|other>",
  "conversation_flow": "<smooth|interrupted|confused>",
  "bot_interruptions": <count>,
  "customer_interruptions": <count>,
  "clarification_requests": <count of clarifying questions>,
  "successful_resolution": <true|false>,
  "confidence_level": <1-5, how confident was bot>,
  "call_sentiment": "<positive|neutral|negative>",
  "key_phrases": [<array of 3-5 important phrases from transcript>]
}}

Focus on:
- Accent: Detect from spelling variations, repeated clarifications, "what?" responses
- Corrections: Customer says "no, actually..." or changes their mind
- Emotions: Detect from language ("this is frustrating", "I don't understand")
- Failure patterns: Why did this call fail? What went wrong?"""

        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}],
            )

            content = response.content[0].text

            # Strip markdown code fences if present
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            return json.loads(content)

        except Exception as e:
            print(f"Error analyzing transcript: {e}")
            return self._get_default_analysis()

    def _get_default_analysis(self) -> dict:
        """Fallback analysis if Claude request fails."""
        return {
            "accent_strength": 3,
            "correction_attempts": 0,
            "emotional_markers": ["neutral"],
            "disfluency_count": 0,
            "background_noise": "none",
            "context_type": "other",
            "failure_pattern": "other",
            "conversation_flow": "smooth",
            "bot_interruptions": 0,
            "customer_interruptions": 0,
            "clarification_requests": 0,
            "successful_resolution": False,
            "confidence_level": 3,
            "call_sentiment": "neutral",
            "key_phrases": [],
        }

    async def batch_analyze(
        self,
        transcripts: list[tuple[str, str, str]],
    ) -> list[dict]:
        """
        Analyze multiple transcripts sequentially.

        Args:
            transcripts: List of (call_id, transcript, outcome) tuples.

        Returns:
            List of analysis results, each with a 'call_id' key added.
        """
        results = []

        for call_id, transcript, outcome in transcripts:
            print(f"  Analyzing call {call_id}...")
            analysis = await self.analyze_transcript(transcript, outcome)
            analysis["call_id"] = call_id
            results.append(analysis)

        return results
