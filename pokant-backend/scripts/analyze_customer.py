"""
Manual analysis script for new customers.

Runs the full pipeline: fetch calls from Vapi, analyze with Claude,
generate embeddings, cluster into patterns.

Usage:
    cd pokant-backend
    python -m scripts.analyze_customer --customer-id=<uuid>
    python -m scripts.analyze_customer --customer-id=<uuid> --limit=100
"""

import asyncio
import argparse
import uuid
from datetime import datetime

from app.database import SessionLocal
from app.models import Customer, Call, CallAttribute
from app.services.vapi import VapiClient
from app.services.claude_analysis import ClaudeAnalyzer
from app.services.pattern_clustering import PatternClusterer
from app.services.encryption import decrypt_value
from app.utils.vectors import generate_embedding


def _determine_outcome(call_data: dict) -> str:
    """Determine if a call succeeded or failed based on Vapi metadata."""
    end_reason = call_data.get("endedReason", "")

    if "assistant-ended-call" in end_reason:
        return "success"
    elif "customer-ended-call" in end_reason:
        # Short calls likely failed
        if call_data.get("duration", 0) < 30:
            return "failed"
        return "success"
    else:
        return "abandoned"


async def analyze_customer(customer_id: str, limit: int = 1000):
    """
    Full analysis pipeline for a customer.

    Steps:
    1. Fetch calls from Vapi
    2. Store in database
    3. Analyze failed calls with Claude
    4. Generate embeddings
    5. Cluster into patterns
    6. Update customer status
    """
    db = SessionLocal()

    try:
        # Get customer
        customer = (
            db.query(Customer)
            .filter(Customer.id == uuid.UUID(customer_id))
            .first()
        )

        if not customer:
            print(f"Customer {customer_id} not found")
            return

        print(f"Starting analysis for {customer.company_name}...")
        print(f"Platform: {customer.bot_provider}")

        # Step 1: Fetch calls from Vapi
        print("\n--- Step 1: Fetching calls from Vapi ---")

        api_key = decrypt_value(customer.vapi_api_key_encrypted)
        vapi = VapiClient(api_key)

        calls_data = await vapi.list_calls(limit=limit)

        print(f"  Retrieved {len(calls_data)} calls")

        # Step 2: Store calls in database
        print("\n--- Step 2: Storing calls ---")

        stored_calls = []
        for call_data in calls_data:
            # Skip if already stored
            existing = (
                db.query(Call)
                .filter(Call.provider_call_id == call_data["id"])
                .first()
            )
            if existing:
                continue

            call = Call(
                id=uuid.uuid4(),
                customer_id=customer.id,
                provider_call_id=call_data["id"],
                transcript=call_data.get("transcript", ""),
                duration_seconds=call_data.get("duration", 0),
                outcome=_determine_outcome(call_data),
                metadata_=call_data,
                created_at=datetime.fromisoformat(
                    call_data["createdAt"].replace("Z", "+00:00")
                ),
            )

            db.add(call)
            stored_calls.append(call)

        db.commit()
        print(f"  Stored {len(stored_calls)} new calls")

        # Step 3: Analyze with Claude
        print("\n--- Step 3: Analyzing transcripts with Claude ---")

        claude = ClaudeAnalyzer()

        # Only analyze failed calls
        failed_calls = [c for c in stored_calls if c.outcome == "failed"]

        if not failed_calls:
            print("  No failed calls to analyze")
            # Still update status and return
            customer.status = "active"
            db.commit()
            print("\nAnalysis complete (no failures detected)")
            return

        print(f"  Analyzing {len(failed_calls)} failed calls...")

        transcripts = [
            (str(c.id), c.transcript or "", c.outcome)
            for c in failed_calls
        ]

        analyses = await claude.batch_analyze(transcripts)

        # Step 4: Generate embeddings and store attributes
        print("\n--- Step 4: Generating embeddings ---")

        for analysis in analyses:
            call_id = uuid.UUID(analysis["call_id"])

            # Get the call transcript for embedding
            call = db.query(Call).filter(Call.id == call_id).first()
            embedding = await generate_embedding(call.transcript or "")

            # Store attributes
            attrs = CallAttribute(
                id=uuid.uuid4(),
                call_id=call_id,
                accent_strength=analysis.get("accent_strength", 3),
                correction_attempts=analysis.get("correction_attempts", 0),
                emotional_markers=analysis.get("emotional_markers", []),
                disfluency_count=analysis.get("disfluency_count", 0),
                background_noise=analysis.get("background_noise", "none"),
                context_type=analysis.get("context_type"),
                failure_pattern=analysis.get("failure_pattern"),
                conversation_flow=analysis.get("conversation_flow"),
                bot_interruptions=analysis.get("bot_interruptions", 0),
                customer_interruptions=analysis.get("customer_interruptions", 0),
                clarification_requests=analysis.get("clarification_requests", 0),
                successful_resolution=analysis.get("successful_resolution", False),
                confidence_level=analysis.get("confidence_level", 3),
                call_sentiment=analysis.get("call_sentiment"),
                key_phrases=analysis.get("key_phrases", []),
                embedding=embedding,
            )

            db.add(attrs)

        db.commit()
        print(f"  Generated {len(analyses)} embeddings")

        # Step 5: Cluster into patterns
        print("\n--- Step 5: Identifying patterns ---")

        clusterer = PatternClusterer(db)
        patterns = clusterer.identify_patterns(customer_id)

        print(f"  Found {len(patterns)} patterns:")
        for p in patterns:
            print(f"    - {p['name']}: {p['frequency']} failures ({p['percentage']:.1f}%)")

        # Save patterns
        pattern_ids = clusterer.save_patterns(customer_id, patterns)

        # Step 6: Update customer status
        customer.status = "active"
        db.commit()

        print(f"\nAnalysis complete!")
        print(f"  Customer ID: {customer_id}")
        print(f"  Total calls: {len(calls_data)}")
        print(f"  Failed calls: {len(failed_calls)}")
        print(f"  Patterns identified: {len(patterns)}")
        print(f"  Pattern IDs: {pattern_ids}")

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()

    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run analysis pipeline for a customer"
    )
    parser.add_argument(
        "--customer-id", required=True, help="Customer UUID"
    )
    parser.add_argument(
        "--limit", type=int, default=1000, help="Max calls to fetch"
    )

    args = parser.parse_args()
    asyncio.run(analyze_customer(args.customer_id, args.limit))
