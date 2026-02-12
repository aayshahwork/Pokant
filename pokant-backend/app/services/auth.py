"""
Simple authentication for customer API access.

Each customer gets an API token for programmatic access.
Frontend uses customer_id directly (no auth for MVP).
"""

import hashlib
import secrets
from typing import Optional

from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Customer

security = HTTPBearer()


def generate_api_token() -> str:
    """Generate secure random API token."""
    return f"pk_{secrets.token_urlsafe(32)}"


def hash_token(token: str) -> str:
    """Hash token for storage (SHA256)."""
    return hashlib.sha256(token.encode()).hexdigest()


def verify_api_token(
    credentials: HTTPAuthorizationCredentials = Security(security),
    db: Session = Depends(get_db),
) -> Customer:
    """
    Verify API token and return customer.

    Usage in route:
        @router.get("/protected")
        def protected_route(customer: Customer = Depends(verify_api_token)):
            return {"customer_id": str(customer.id)}
    """
    token = credentials.credentials

    if not token.startswith("pk_"):
        raise HTTPException(
            status_code=401,
            detail="Invalid token format",
        )

    token_hash = hash_token(token)

    customer = (
        db.query(Customer)
        .filter(Customer.api_token_hash == token_hash)
        .first()
    )

    if not customer:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
        )

    return customer


def get_optional_customer(
    db: Session = Depends(get_db),
    credentials: Optional[HTTPAuthorizationCredentials] = Security(
        HTTPBearer(auto_error=False)
    ),
) -> Optional[Customer]:
    """
    Optional auth - returns customer if token provided, None otherwise.

    Useful for endpoints that work with/without auth.
    """
    if not credentials:
        return None

    try:
        return verify_api_token(credentials, db)
    except HTTPException:
        return None
