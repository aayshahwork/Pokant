from pydantic import BaseModel, EmailStr
from typing import Optional
from uuid import UUID
from datetime import date, datetime


# --- Customer ---
class CustomerCreate(BaseModel):
    company_name: str
    email: EmailStr
    bot_provider: str = "vapi"
    bot_id: Optional[str] = None
    vapi_api_key: Optional[str] = None
    retell_api_key: Optional[str] = None


class CustomerResponse(BaseModel):
    id: UUID
    company_name: str
    email: str
    bot_provider: str
    bot_id: Optional[str]
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class OnboardResponse(BaseModel):
    """Returned once on onboarding; includes API token (never stored plain)."""

    customer_id: str
    api_token: str
    status: str
    message: str


# --- Dashboard ---
class DashboardStats(BaseModel):
    total_calls: int
    success_rate: float
    avg_duration: float
    failure_categories: dict[str, int]
    recent_calls: list[dict]
    trend_data: list[dict]


# --- Pattern ---
class PatternResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    failure_type: Optional[str]
    frequency: int
    severity: str
    revenue_impact_monthly: Optional[float] = None
    root_cause: Optional[str] = None
    suggested_fix: Optional[str] = None
    status: Optional[str] = "identified"
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Variant ---
class VariantCreate(BaseModel):
    pattern_id: UUID
    name: str
    prompt_text: str
    is_control: bool = False


class VariantResponse(BaseModel):
    id: UUID
    pattern_id: UUID
    letter: Optional[str] = None
    name: str
    prompt_text: str
    success_rate: float
    improvement_delta: float
    recommended: bool
    tested_against: int
    created_at: datetime

    model_config = {"from_attributes": True}


# --- A/B Test ---
class ABTestDeployRequest(BaseModel):
    customer_id: str
    pattern_id: str
    variant_id: str
    traffic_split: Optional[int] = 20


class ABTestResponse(BaseModel):
    id: UUID
    customer_id: UUID
    pattern_id: UUID
    name: str
    status: str
    control_assistant_id: Optional[str] = None
    variant_assistant_id: Optional[str] = None
    traffic_split: int
    total_calls: int
    control_calls: int
    control_success_rate: float
    variant_calls: int
    variant_success_rate: float
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    winner_variant_id: Optional[UUID] = None
    created_at: datetime

    model_config = {"from_attributes": True}
