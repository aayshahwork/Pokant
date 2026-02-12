import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ABTest
from app.schemas import ABTestDeployRequest, ABTestResponse
from app.services.ab_test_manager import ABTestManager
from app.services.statistical_analyzer import StatisticalAnalyzer

router = APIRouter()


@router.post("/tests/deploy")
async def deploy_ab_test(
    request: ABTestDeployRequest,
    db: Session = Depends(get_db),
):
    """
    Deploy an A/B test for a variant.

    Creates a variant assistant in Vapi and starts monitoring.
    """
    manager = ABTestManager(db)

    try:
        test_id = await manager.deploy_test(
            customer_id=request.customer_id,
            pattern_id=request.pattern_id,
            variant_id=request.variant_id,
            traffic_split=request.traffic_split or 20,
        )
        return {
            "test_id": test_id,
            "status": "deployed",
            "message": "A/B test started. Check back in 24 hours for early results.",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from None


@router.get("/tests/{test_id}")
async def get_test_results(
    test_id: str,
    db: Session = Depends(get_db),
):
    """
    Get current A/B test results.

    Fetches latest call data from Vapi, calculates statistical
    significance, and projects annual revenue impact.
    """
    try:
        tid = uuid.UUID(test_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid test_id") from None

    test = db.query(ABTest).filter(ABTest.id == tid).first()
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")

    manager = ABTestManager(db)
    analyzer = StatisticalAnalyzer()

    try:
        results = await manager.fetch_results(test_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None

    # Statistical significance
    ctrl = results["control"]
    var = results["variant"]
    significance = analyzer.calculate_significance(
        control_successes=ctrl["successes"],
        control_total=ctrl["calls"],
        variant_successes=var["successes"],
        variant_total=var["calls"],
    )

    # Revenue impact projection
    impact = analyzer.project_annual_impact(
        monthly_calls=max(test.total_calls * 30 // max(results["days_running"], 1), 100),
        improvement_rate=significance["improvement"] / 100 if significance["improvement"] > 0 else 0,
    )

    return {
        **results,
        "statistical_analysis": significance,
        "projected_impact": impact,
    }


@router.post("/tests/{test_id}/promote")
async def promote_variant(
    test_id: str,
    db: Session = Depends(get_db),
):
    """
    Promote winning variant to 100% traffic.

    Updates the main assistant's prompt and cleans up the variant.
    """
    manager = ABTestManager(db)

    try:
        result = await manager.promote_winner(test_id)
        return {"success": True, **result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from None


@router.post("/tests/{test_id}/cancel")
async def cancel_test(
    test_id: str,
    db: Session = Depends(get_db),
):
    """Cancel a running A/B test and clean up resources."""
    manager = ABTestManager(db)

    try:
        await manager.cancel_test(test_id)
        return {"message": "Test cancelled"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None


@router.get("/tests", response_model=list[ABTestResponse])
async def list_tests(
    customer_id: str,
    db: Session = Depends(get_db),
):
    """List all A/B tests for a customer."""
    try:
        cid = uuid.UUID(customer_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid customer_id") from None

    tests = (
        db.query(ABTest)
        .filter(ABTest.customer_id == cid)
        .order_by(ABTest.created_at.desc())
        .all()
    )
    return tests
