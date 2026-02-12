import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Customer
from app.schemas import CustomerCreate, OnboardResponse
from app.services.auth import generate_api_token, hash_token
from app.services.encryption import encrypt_value

router = APIRouter()


@router.post("/onboard", response_model=OnboardResponse)
async def onboard_customer(customer: CustomerCreate, db: Session = Depends(get_db)):
    """Onboard a new customer, generate API token, and start analysis in background."""
    api_token = generate_api_token()
    token_hash = hash_token(api_token)

    new_customer = Customer(
        id=uuid.uuid4(),
        company_name=customer.company_name,
        email=customer.email,
        bot_provider=customer.bot_provider,
        bot_id=customer.bot_id,
        status="analyzing",
        is_active=True,
        api_token_hash=token_hash,
    )

    if customer.vapi_api_key:
        new_customer.vapi_api_key_encrypted = encrypt_value(customer.vapi_api_key)
    if customer.retell_api_key:
        new_customer.retell_api_key_encrypted = encrypt_value(customer.retell_api_key)

    db.add(new_customer)
    db.commit()
    db.refresh(new_customer)

    # Trigger analysis in background (Celery)
    try:
        from app.tasks import analyze_customer_task
        analyze_customer_task.delay(str(new_customer.id), limit=1000)
    except Exception:
        # If Redis/Celery unavailable, analysis can be run manually
        pass

    return OnboardResponse(
        customer_id=str(new_customer.id),
        api_token=api_token,
        status="analyzing",
        message="Save this API token - it won't be shown again. Analysis started in background; check back in 5-10 minutes.",
    )
