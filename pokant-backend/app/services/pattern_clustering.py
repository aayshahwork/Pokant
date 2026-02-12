"""
Cluster similar call failures into patterns.

Groups failed calls by their failure_pattern attribute,
calculates statistics, and stores patterns in the database.
"""

import uuid
from collections import Counter
from typing import Optional

from sqlalchemy.orm import Session

from app.models import Call, CallAttribute, Pattern


class PatternClusterer:
    def __init__(self, db: Session):
        self.db = db

    def identify_patterns(self, customer_id: str) -> list[dict]:
        """
        Identify top failure patterns for a customer.

        Args:
            customer_id: Customer UUID string.

        Returns:
            List of pattern dicts with stats and examples.
        """
        # Get all failed calls with attributes
        failed_calls = (
            self.db.query(Call, CallAttribute)
            .join(CallAttribute, Call.id == CallAttribute.call_id)
            .filter(Call.customer_id == uuid.UUID(customer_id))
            .filter(Call.outcome == "failed")
            .all()
        )

        if not failed_calls:
            return []

        # Count failure patterns
        pattern_counts: Counter = Counter()
        pattern_examples: dict[str, str] = {}
        pattern_calls: dict[str, list] = {}

        for call, attrs in failed_calls:
            pattern = attrs.failure_pattern or "other"
            pattern_counts[pattern] += 1

            if pattern not in pattern_examples:
                pattern_examples[pattern] = call.transcript or ""
                pattern_calls[pattern] = []

            pattern_calls[pattern].append((call.id, attrs))

        # Get top 5 patterns
        top_patterns = pattern_counts.most_common(5)

        results = []
        for pattern_name, frequency in top_patterns:
            calls_with_pattern = pattern_calls[pattern_name]

            avg_accent = sum(
                a.accent_strength or 0 for _, a in calls_with_pattern
            ) / len(calls_with_pattern)
            avg_corrections = sum(
                a.correction_attempts or 0 for _, a in calls_with_pattern
            ) / len(calls_with_pattern)

            # Estimate revenue impact ($20 per failed call)
            revenue_impact = frequency * 20

            results.append({
                "name": self._format_pattern_name(pattern_name),
                "failure_pattern": pattern_name,
                "frequency": frequency,
                "percentage": (frequency / len(failed_calls)) * 100,
                "revenue_impact_monthly": revenue_impact,
                "example_transcript": (pattern_examples[pattern_name] or "")[:500],
                "avg_accent_strength": round(avg_accent, 1),
                "avg_correction_attempts": round(avg_corrections, 1),
                "call_ids": [str(call_id) for call_id, _ in calls_with_pattern[:10]],
            })

        return results

    def _format_pattern_name(self, pattern: str) -> str:
        """Convert snake_case to Title Case."""
        return pattern.replace("_", " ").title()

    def save_patterns(
        self,
        customer_id: str,
        patterns: list[dict],
    ) -> list[str]:
        """
        Save identified patterns to the database.

        Returns:
            List of created pattern ID strings.
        """
        pattern_ids = []

        for p in patterns:
            pattern = Pattern(
                id=uuid.uuid4(),
                customer_id=uuid.UUID(customer_id),
                name=p["name"],
                description=f"Occurs in {p['percentage']:.1f}% of failed calls",
                failure_type=p["failure_pattern"],
                frequency=p["frequency"],
                severity=self._infer_severity(p["frequency"], p["percentage"]),
                revenue_impact_monthly=p["revenue_impact_monthly"],
                example_transcript=p["example_transcript"],
                example_call_ids=p["call_ids"],
                root_cause=self._infer_root_cause(p),
                status="identified",
            )

            self.db.add(pattern)
            pattern_ids.append(str(pattern.id))

        self.db.commit()
        return pattern_ids

    def _infer_severity(self, frequency: int, percentage: float) -> str:
        """Infer severity from frequency and percentage."""
        if percentage >= 30 or frequency >= 50:
            return "critical"
        elif percentage >= 15 or frequency >= 20:
            return "high"
        elif percentage >= 5 or frequency >= 10:
            return "medium"
        return "low"

    def _infer_root_cause(self, pattern: dict) -> str:
        """Infer root cause from pattern data."""
        root_causes = {
            "customer_changes_mind": "Bot doesn't recognize correction attempts",
            "complex_scheduling": "Bot can't handle multi-step workflows",
            "unclear_availability": "Bot gives vague or incomplete responses",
            "bot_confusion": "Bot loses context mid-conversation",
            "other": "Multiple contributing factors - needs manual review",
        }
        return root_causes.get(pattern["failure_pattern"], "Needs manual review")
