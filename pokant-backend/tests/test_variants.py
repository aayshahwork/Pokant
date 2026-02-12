"""
Test variant generation.
"""

import pytest

from app.database import SessionLocal
from app.models import Customer, Pattern
from app.services.variant_generator import VariantGenerator


@pytest.mark.asyncio
async def test_generate_variants():
    """Test GPT-4 variant generation returns 5 variants with letter and prompt_text."""
    db = SessionLocal()

    try:
        customer = Customer(
            company_name="Test Co",
            email="variantstest@example.com",
            bot_provider="vapi",
            status="active",
        )
        db.add(customer)
        db.commit()
        db.refresh(customer)

        pattern = Pattern(
            customer_id=customer.id,
            name="Customer Changes Mind",
            description="Test pattern for variant generation",
            frequency=100,
            revenue_impact_monthly=2000.0,
            example_transcript="Customer said they would call back later.",
            root_cause="Bot doesn't handle corrections",
            status="identified",
        )
        db.add(pattern)
        db.commit()
        db.refresh(pattern)

        generator = VariantGenerator(db)
        variants = await generator.generate_variants(str(pattern.id))

        assert len(variants) == 5
        assert all("letter" in v for v in variants)
        assert all("prompt_text" in v for v in variants)
        letters = [v["letter"] for v in variants]
        assert set(letters) >= {"A", "B", "C", "D", "E"}
    finally:
        db.close()
