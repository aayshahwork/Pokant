import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Pattern, Variant
from app.schemas import VariantCreate, VariantResponse
from app.services.variant_manager import VariantManager

router = APIRouter()


@router.get("/variants/{pattern_id}", response_model=List[VariantResponse])
async def get_variants(
    pattern_id: str,
    db: Session = Depends(get_db),
):
    """
    Get variants for a pattern.

    If variants don't exist yet, generate + test them automatically.
    """

    try:
        pid = uuid.UUID(pattern_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid pattern_id") from None

    pattern = db.query(Pattern).filter(Pattern.id == pid).first()
    if not pattern:
        raise HTTPException(status_code=404, detail="Pattern not found")

    variants = (
        db.query(Variant)
        .filter(Variant.pattern_id == pid)
        .order_by(Variant.success_rate.desc())
        .all()
    )

    if not variants:
        # No variants yet – run full pipeline
        manager = VariantManager(db)
        await manager.create_variants_for_pattern(pattern_id)

        variants = manager.get_variants(pattern_id)

    return variants


@router.post("/variants/{pattern_id}/regenerate")
async def regenerate_variants(
    pattern_id: str,
    db: Session = Depends(get_db),
):
    """
    Force regenerate variants for a pattern (delete old ones).
    """

    try:
        pid = uuid.UUID(pattern_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid pattern_id") from None

    # Delete existing variants
    db.query(Variant).filter(Variant.pattern_id == pid).delete()
    db.commit()

    manager = VariantManager(db)
    variant_ids = await manager.create_variants_for_pattern(pattern_id)

    return {
        "message": "Variants regenerated",
        "variant_ids": variant_ids,
    }


@router.get("/variants/detail/{variant_id}", response_model=VariantResponse)
async def get_variant_detail(
    variant_id: str,
    db: Session = Depends(get_db),
):
    """Get details for a single variant."""

    try:
        vid = uuid.UUID(variant_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid variant_id") from None

    variant = db.query(Variant).filter(Variant.id == vid).first()
    if not variant:
        raise HTTPException(status_code=404, detail="Variant not found")

    return variant


@router.post("/variants", response_model=VariantResponse)
async def create_variant(
    variant: VariantCreate,
    db: Session = Depends(get_db),
):
    """
    Manual variant creation endpoint (primarily for testing/tools).
    """

    vid = uuid.uuid4()
    db_variant = Variant(
        id=vid,
        pattern_id=variant.pattern_id,
        letter=None,
        name=variant.name,
        prompt_text=variant.prompt_text,
        is_control=variant.is_control,
        success_rate=0.0,
        improvement_delta=0.0,
        recommended=False,
        tested_against=0,
        total_calls=0,
    )
    db.add(db_variant)
    db.commit()
    db.refresh(db_variant)

    return db_variant

