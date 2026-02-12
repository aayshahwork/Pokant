import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    Date,
    String,
    Float,
    Integer,
    Boolean,
    DateTime,
    Text,
    ForeignKey,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from pgvector.sqlalchemy import Vector

from app.database import Base


class Customer(Base):
    __tablename__ = "customers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    vapi_api_key_encrypted = Column(Text)
    retell_api_key_encrypted = Column(Text)
    bot_provider = Column(String(50), default="vapi")
    bot_id = Column(String(255))
    status = Column(String(20), default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    # API token (hashed) for programmatic access
    api_token_hash = Column(String(64), unique=True, nullable=True)
    last_active_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_customers_email", "email"),
    )


class Call(Base):
    __tablename__ = "calls"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)
    provider_call_id = Column(String(255))
    transcript = Column(Text)
    duration_seconds = Column(Float)
    outcome = Column(String(50))
    sentiment_score = Column(Float)
    failure_category = Column(String(100))
    metadata_ = Column("metadata", JSONB, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    test_id = Column(UUID(as_uuid=True), ForeignKey("ab_tests.id"), nullable=True)
    variant_id = Column(UUID(as_uuid=True), ForeignKey("variants.id"), nullable=True)

    __table_args__ = (
        Index("ix_calls_customer_id", "customer_id"),
        Index("ix_calls_created_at", "created_at"),
        Index("ix_calls_failure_category", "failure_category"),
    )


class CallAttribute(Base):
    __tablename__ = "call_attributes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    call_id = Column(UUID(as_uuid=True), ForeignKey("calls.id"), nullable=False)

    # 15 Claude-extracted analysis attributes
    accent_strength = Column(Integer, default=1)
    correction_attempts = Column(Integer, default=0)
    emotional_markers = Column(JSONB, default=[])
    disfluency_count = Column(Integer, default=0)
    background_noise = Column(String(20), default="none")
    context_type = Column(String(50))
    failure_pattern = Column(String(100))
    conversation_flow = Column(String(20))
    bot_interruptions = Column(Integer, default=0)
    customer_interruptions = Column(Integer, default=0)
    clarification_requests = Column(Integer, default=0)
    successful_resolution = Column(Boolean, default=False)
    confidence_level = Column(Integer, default=3)
    call_sentiment = Column(String(20))
    key_phrases = Column(JSONB, default=[])

    # Vector embedding for semantic search
    embedding = Column(Vector(1536))

    __table_args__ = (
        Index("ix_call_attributes_call_id", "call_id"),
        Index("ix_call_attributes_failure_pattern", "failure_pattern"),
        Index(
            "ix_call_attributes_embedding",
            "embedding",
            postgresql_using="ivfflat",
            postgresql_with={"lists": 100},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


class Pattern(Base):
    __tablename__ = "patterns"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    failure_type = Column(String(100))
    frequency = Column(Integer, default=0)
    severity = Column(String(20), default="medium")
    revenue_impact_monthly = Column(Float, default=0.0)
    example_call_ids = Column(JSONB, default=[])
    example_transcript = Column(Text)
    suggested_fix = Column(Text)
    root_cause = Column(Text)
    status = Column(String(20), default="identified")
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_patterns_customer_id", "customer_id"),
        Index("ix_patterns_severity", "severity"),
    )


class Variant(Base):
    __tablename__ = "variants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pattern_id = Column(UUID(as_uuid=True), ForeignKey("patterns.id"), nullable=False)
    # Letter label used in UI (A-E)
    letter = Column(String(1), nullable=True)
    name = Column(String(255), nullable=False)
    prompt_text = Column(Text, nullable=False)

    # A/B testing state
    is_control = Column(Boolean, default=False)
    total_calls = Column(Integer, default=0)

    # Offline simulation metrics (Week 3 optimization layer)
    success_rate = Column(Float, default=0.0)
    improvement_delta = Column(Float, default=0.0)
    recommended = Column(Boolean, default=False)
    tested_against = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_variants_pattern_id", "pattern_id"),
    )


class ABTest(Base):
    __tablename__ = "ab_tests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)
    pattern_id = Column(UUID(as_uuid=True), ForeignKey("patterns.id"), nullable=False)
    name = Column(String(255), nullable=False)
    status = Column(String(20), default="draft")
    variant_ids = Column(JSONB, default={})

    # Vapi deployment state
    control_assistant_id = Column(String(255))
    variant_assistant_id = Column(String(255))
    traffic_split = Column(Integer, default=20)

    # Monitoring metrics
    total_calls = Column(Integer, default=0)
    control_calls = Column(Integer, default=0)
    control_success_rate = Column(Float, default=0.0)
    variant_calls = Column(Integer, default=0)
    variant_success_rate = Column(Float, default=0.0)

    # Timeline
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    winner_variant_id = Column(UUID(as_uuid=True), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_ab_tests_customer_id", "customer_id"),
        Index("ix_ab_tests_status", "status"),
    )
