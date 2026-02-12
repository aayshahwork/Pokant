"""
Manage variant lifecycle: generate -> test -> store.
"""

from __future__ import annotations

import uuid
from typing import List

from sqlalchemy.orm import Session

from app.models import Variant
from app.services.variant_generator import VariantGenerator
from app.services.variant_tester import VariantTester


class VariantManager:
    """
    Orchestrates the Week 3 optimization layer:
    1. Generate variants with GPT-4o
    2. Test them against historical edge cases with Claude
    3. Persist the results in the variants table
    """

    def __init__(self, db: Session):
        self.db = db
        self.generator = VariantGenerator(db)
        self.tester = VariantTester(db)

    async def create_variants_for_pattern(self, pattern_id: str) -> List[str]:
        """
        Full pipeline: generate -> test -> store.

        Returns:
            List of created Variant IDs (as strings).
        """

        print(f"Creating variants for pattern {pattern_id}...")

        # Step 1: Generate with GPT-4
        print("1️⃣ Generating variants with GPT-4o...")
        variants_data = await self.generator.generate_variants(pattern_id)
        print(f"   Generated {len(variants_data)} raw variants")

        # Step 2: Test with Claude
        print("2️⃣ Testing variants against edge cases...")
        tested_variants = await self.tester.test_variants(pattern_id, variants_data)
        print("   Testing complete")

        # Step 3: Store in database
        print("3️⃣ Storing variants...")
        variant_ids: List[str] = []

        for v in tested_variants:
            vid = uuid.uuid4()
            variant = Variant(
                id=vid,
                pattern_id=uuid.UUID(pattern_id),
                letter=v.get("letter"),
                name=v.get("name", f"Variant {v.get('letter', '')}"),
                prompt_text=v.get("prompt_text", ""),
                is_control=False,
                success_rate=v.get("success_rate", 0.0),
                improvement_delta=v.get("improvement_delta", 0.0),
                recommended=v.get("recommended", False),
                tested_against=v.get("tested_against", 0),
                total_calls=0,
            )

            self.db.add(variant)
            variant_ids.append(str(vid))

        self.db.commit()

        print(f"✅ Created {len(variant_ids)} variants for pattern {pattern_id}")

        return variant_ids

    def get_variants(self, pattern_id: str) -> List[Variant]:
        """
        Get all variants for a pattern, ordered by simulated success_rate.
        """

        return (
            self.db.query(Variant)
            .filter(Variant.pattern_id == uuid.UUID(pattern_id))
            .order_by(Variant.success_rate.desc())
            .all()
        )

