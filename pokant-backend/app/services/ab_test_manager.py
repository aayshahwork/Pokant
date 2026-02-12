"""
Manage A/B test lifecycle: deploy -> monitor -> analyze -> promote.
"""

import uuid
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models import ABTest, Customer, Pattern, Variant
from app.services.encryption import decrypt_value
from app.services.vapi import VapiClient


class ABTestManager:
    def __init__(self, db: Session):
        self.db = db

    async def deploy_test(
        self,
        customer_id: str,
        pattern_id: str,
        variant_id: str,
        traffic_split: int = 20,
    ) -> str:
        """
        Deploy an A/B test.

        Steps:
        1. Validate customer, variant, pattern
        2. Create variant assistant in Vapi
        3. Create ABTest record
        4. Return test ID

        Traffic routing happens at the webhook level. For MVP,
        manually route the configured % of calls to the variant assistant.
        """
        customer = (
            self.db.query(Customer)
            .filter(Customer.id == uuid.UUID(customer_id))
            .first()
        )
        if not customer:
            raise ValueError("Customer not found")

        variant = (
            self.db.query(Variant)
            .filter(Variant.id == uuid.UUID(variant_id))
            .first()
        )
        if not variant:
            raise ValueError("Variant not found")

        pattern = (
            self.db.query(Pattern)
            .filter(Pattern.id == uuid.UUID(pattern_id))
            .first()
        )
        if not pattern:
            raise ValueError("Pattern not found")

        # Create variant assistant in Vapi
        api_key = decrypt_value(customer.vapi_api_key_encrypted)
        vapi = VapiClient(api_key)

        variant_assistant = await vapi.create_assistant_variant(
            base_assistant_id=customer.bot_id,
            variant_prompt=variant.prompt_text,
            variant_name=f"Variant {variant.letter or 'X'}",
        )

        variant_assistant_id = variant_assistant["id"]
        now = datetime.utcnow()

        test = ABTest(
            id=uuid.uuid4(),
            customer_id=customer.id,
            pattern_id=pattern.id,
            name=f"{pattern.name} - Variant {variant.letter or 'X'} Test",
            status="running",
            variant_ids={
                "control": customer.bot_id,
                "variant": variant_assistant_id,
                "variant_db_id": str(variant.id),
                "variant_letter": variant.letter,
            },
            control_assistant_id=customer.bot_id,
            variant_assistant_id=variant_assistant_id,
            traffic_split=traffic_split,
            start_date=now.date(),
            end_date=(now + timedelta(days=4)).date(),
            started_at=now,
        )

        self.db.add(test)
        self.db.commit()

        return str(test.id)

    async def fetch_results(self, test_id: str) -> dict:
        """
        Fetch current test results from Vapi.

        Queries both control and variant assistants for calls since
        the test start, calculates success rates, and updates the record.
        """
        test = (
            self.db.query(ABTest)
            .filter(ABTest.id == uuid.UUID(test_id))
            .first()
        )
        if not test:
            raise ValueError("Test not found")

        customer = (
            self.db.query(Customer)
            .filter(Customer.id == test.customer_id)
            .first()
        )

        api_key = decrypt_value(customer.vapi_api_key_encrypted)
        vapi = VapiClient(api_key)

        start_dt = datetime.combine(test.start_date, datetime.min.time())

        control_calls = await vapi.get_calls_by_assistant(
            assistant_id=test.control_assistant_id,
            created_after=start_dt,
            limit=1000,
        )
        variant_calls = await vapi.get_calls_by_assistant(
            assistant_id=test.variant_assistant_id,
            created_after=start_dt,
            limit=1000,
        )

        control_success = sum(
            1
            for c in control_calls
            if c.get("endedReason") == "assistant-ended-call"
        )
        control_total = len(control_calls)
        control_rate = (
            (control_success / control_total * 100) if control_total else 0.0
        )

        variant_success = sum(
            1
            for c in variant_calls
            if c.get("endedReason") == "assistant-ended-call"
        )
        variant_total = len(variant_calls)
        variant_rate = (
            (variant_success / variant_total * 100) if variant_total else 0.0
        )

        # Persist monitoring snapshot
        test.control_calls = control_total
        test.control_success_rate = round(control_rate, 1)
        test.variant_calls = variant_total
        test.variant_success_rate = round(variant_rate, 1)
        test.total_calls = control_total + variant_total
        self.db.commit()

        days_running = (datetime.utcnow().date() - test.start_date).days

        return {
            "test_id": test_id,
            "status": test.status,
            "days_running": days_running,
            "days_remaining": max(0, 4 - days_running),
            "traffic_split": test.traffic_split,
            "control": {
                "assistant_id": test.control_assistant_id,
                "calls": control_total,
                "successes": control_success,
                "success_rate": round(control_rate, 1),
            },
            "variant": {
                "assistant_id": test.variant_assistant_id,
                "letter": (test.variant_ids or {}).get("variant_letter"),
                "calls": variant_total,
                "successes": variant_success,
                "success_rate": round(variant_rate, 1),
            },
        }

    async def promote_winner(self, test_id: str) -> dict:
        """
        Promote winning variant to 100% traffic.

        Steps:
        1. Verify variant outperformed control
        2. Update main assistant prompt in Vapi
        3. Delete the variant assistant
        4. Mark test as complete and pattern as fixed
        """
        test = (
            self.db.query(ABTest)
            .filter(ABTest.id == uuid.UUID(test_id))
            .first()
        )
        if not test:
            raise ValueError("Test not found")
        if test.status != "running":
            raise ValueError(f"Test is '{test.status}', expected 'running'")

        # Fetch latest numbers
        results = await self.fetch_results(test_id)

        if results["variant"]["success_rate"] <= results["control"]["success_rate"]:
            raise ValueError(
                "Variant did not outperform control "
                f"({results['variant']['success_rate']}% vs "
                f"{results['control']['success_rate']}%)"
            )

        # Resolve the variant record
        variant_db_id = (test.variant_ids or {}).get("variant_db_id")
        variant = (
            self.db.query(Variant)
            .filter(Variant.id == uuid.UUID(variant_db_id))
            .first()
        ) if variant_db_id else None

        if not variant:
            raise ValueError("Variant record not found in database")

        customer = (
            self.db.query(Customer)
            .filter(Customer.id == test.customer_id)
            .first()
        )

        api_key = decrypt_value(customer.vapi_api_key_encrypted)
        vapi = VapiClient(api_key)

        # Update main assistant with winning prompt
        await vapi.update_assistant_prompt(
            assistant_id=customer.bot_id,
            new_prompt=variant.prompt_text,
        )

        # Clean up variant assistant
        try:
            await vapi.delete_assistant(test.variant_assistant_id)
        except Exception:
            pass  # Best-effort cleanup

        # Update records
        test.status = "complete"
        test.winner_variant_id = variant.id
        test.completed_at = datetime.utcnow()

        pattern = (
            self.db.query(Pattern)
            .filter(Pattern.id == test.pattern_id)
            .first()
        )
        if pattern:
            pattern.status = "fixed"

        self.db.commit()

        improvement = (
            results["variant"]["success_rate"] - results["control"]["success_rate"]
        )

        return {
            "message": "Variant promoted successfully",
            "variant_letter": variant.letter,
            "variant_success_rate": results["variant"]["success_rate"],
            "control_success_rate": results["control"]["success_rate"],
            "improvement": round(improvement, 1),
        }

    async def cancel_test(self, test_id: str) -> None:
        """Cancel a running test and clean up the variant assistant."""
        test = (
            self.db.query(ABTest)
            .filter(ABTest.id == uuid.UUID(test_id))
            .first()
        )
        if not test:
            raise ValueError("Test not found")

        # Best-effort cleanup of variant assistant
        if test.variant_assistant_id:
            try:
                customer = (
                    self.db.query(Customer)
                    .filter(Customer.id == test.customer_id)
                    .first()
                )
                api_key = decrypt_value(customer.vapi_api_key_encrypted)
                vapi = VapiClient(api_key)
                await vapi.delete_assistant(test.variant_assistant_id)
            except Exception:
                pass

        test.status = "cancelled"
        test.completed_at = datetime.utcnow()
        self.db.commit()
