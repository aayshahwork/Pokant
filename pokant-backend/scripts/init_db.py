"""
Database initialization and test data seeding script.

Usage:
    cd pokant-backend
    python -m scripts.init_db
"""
import uuid
from datetime import datetime, timedelta
import random
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import engine, SessionLocal, Base
from app import models


def create_tables():
    """Create all tables (skips pgvector extension if not available)."""
    print("Creating tables...")
    Base.metadata.create_all(bind=engine)
    print("Tables created successfully.")


def seed_test_data():
    """Insert test data for development."""
    db = SessionLocal()
    try:
        # Check if data already exists
        existing = db.query(models.Customer).first()
        if existing:
            print("Test data already exists, skipping seed.")
            return

        # Create a test customer
        customer = models.Customer(
            id=uuid.uuid4(),
            company_name="Acme Support Co",
            email="demo@acme-support.com",
            bot_provider="vapi",
            bot_id="bot-demo-001",
            is_active=True,
        )
        db.add(customer)
        db.flush()

        # Create some patterns
        patterns_data = [
            {
                "name": "Escalation Request Handling",
                "description": "Bot fails to properly route customers requesting supervisor escalation",
                "failure_type": "Customer Requests Escalation",
                "frequency": 42,
                "severity": "critical",
                "revenue_impact_monthly": 840.0,
                "root_cause": "Bot doesn't recognize correction attempts",
                "suggested_fix": "Add escalation detection with immediate warm transfer to live agent",
                "status": "identified",
            },
            {
                "name": "Complex Multi-Issue Inquiry",
                "description": "Bot loses context when customer raises multiple issues in one call",
                "failure_type": "Complex Inquiry",
                "frequency": 28,
                "severity": "high",
                "revenue_impact_monthly": 560.0,
                "root_cause": "Bot can't handle multi-step workflows",
                "suggested_fix": "Implement issue queuing - acknowledge all issues, resolve sequentially",
                "status": "identified",
            },
            {
                "name": "Account Verification Loop",
                "description": "Bot repeatedly asks for verification details already provided",
                "failure_type": "Account Verification",
                "frequency": 19,
                "severity": "medium",
                "revenue_impact_monthly": 380.0,
                "root_cause": "Bot loses context mid-conversation",
                "suggested_fix": "Cache verified identity data within the session context",
                "status": "identified",
            },
        ]

        patterns = []
        for p_data in patterns_data:
            pattern = models.Pattern(
                id=uuid.uuid4(),
                customer_id=customer.id,
                **p_data,
            )
            db.add(pattern)
            patterns.append(pattern)

        db.flush()

        # Create variants for the first pattern
        control = models.Variant(
            id=uuid.uuid4(),
            pattern_id=patterns[0].id,
            name="Control - Current Prompt",
            prompt_text="You are a customer service assistant. Help the customer with their request.",
            is_control=True,
            success_rate=73.2,
            total_calls=500,
        )
        variant_a = models.Variant(
            id=uuid.uuid4(),
            pattern_id=patterns[0].id,
            name="Variant A - Empathy First",
            prompt_text="You are an empathetic customer service assistant. Always acknowledge the customer's frustration before problem-solving.",
            is_control=False,
            success_rate=81.5,
            total_calls=250,
        )
        db.add_all([control, variant_a])
        db.flush()

        # Create sample calls
        outcomes = ["success", "success", "success", "failure"]
        failure_categories = [
            "Customer Requests Escalation",
            "Complex Inquiry",
            "Account Verification",
            "Unclear Issue Description",
        ]

        for i in range(20):
            outcome = random.choice(outcomes)
            call = models.Call(
                id=uuid.uuid4(),
                customer_id=customer.id,
                provider_call_id=f"vapi-call-{i:04d}",
                transcript=f"Sample transcript for call {i}",
                duration_seconds=round(random.uniform(60, 420), 1),
                outcome=outcome,
                sentiment_score=round(random.uniform(0.2, 0.95), 2),
                failure_category=random.choice(failure_categories) if outcome == "failure" else None,
                created_at=datetime.utcnow() - timedelta(hours=random.randint(1, 168)),
            )
            db.add(call)

        db.commit()
        print(f"Seeded: 1 customer, {len(patterns)} patterns, 2 variants, 20 calls")

    except Exception as e:
        db.rollback()
        print(f"Error seeding data: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    create_tables()
    seed_test_data()
    print("Database initialization complete.")
