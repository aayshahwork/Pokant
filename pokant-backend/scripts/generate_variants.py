"""
Generate and test prompt variants for a failure pattern.

Usage:
    python scripts/generate_variants.py --pattern-id=<uuid>
"""

from __future__ import annotations

import argparse
import asyncio

from app.database import SessionLocal
from app.services.variant_manager import VariantManager


async def generate_variants(pattern_id: str) -> None:
    """Generate and test variants for a pattern, then print results."""

    db = SessionLocal()

    try:
        manager = VariantManager(db)
        variant_ids = await manager.create_variants_for_pattern(pattern_id)

        print(f"\n✅ Generated {len(variant_ids)} variants")
        print(f"Variant IDs: {variant_ids}")

        variants = manager.get_variants(pattern_id)

        print("\nResults (best first):")
        for v in variants:
            star = "⭐" if getattr(v, "recommended", False) else " "
            print(f"{star} Variant {getattr(v, 'letter', '?')}: {v.name}")
            print(
                f"   Success: {v.success_rate:.1f}% "
                f"({getattr(v, 'improvement_delta', 0.0):+0.1f}%)"
            )
            print(f"   Tested against: {getattr(v, 'tested_against', 0)} edge cases")
            print()

    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--pattern-id", required=True)

    args = parser.parse_args()

    asyncio.run(generate_variants(args.pattern_id))

