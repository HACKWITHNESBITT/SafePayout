from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RunStatus(StrEnum):
    DRAFT = "DRAFT"
    REVIEW = "REVIEW"
    APPROVED = "APPROVED"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class PolicyDecision(StrEnum):
    AUTO_APPROVED = "AUTO_APPROVED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    BLOCKED = "BLOCKED"


class HumanDecision(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class PayPalItemStatus(StrEnum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    UNCLAIMED = "UNCLAIMED"
    BLOCKED = "BLOCKED"
    REFUNDED = "REFUNDED"
    REVERSED = "REVERSED"


class PayoutRunCreate(BaseModel):
    budget_cap: Decimal | None = Field(None, ge=0, description="Maximum total amount for this run")
    raw_text: str | None = Field(None, description="Free-text input for payouts")
    raw_csv: str | None = Field(None, description="CSV content for payouts")


class PayoutRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: RunStatus
    budget_cap: Decimal | None
    created_at: datetime
    updated_at: datetime
    sender_batch_id: str
    paypal_batch_id: str | None


class PayoutItemBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    amount: Decimal = Field(..., ge=0, max_digits=18, decimal_places=2)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    note: str | None = None


class PayoutItemCreate(PayoutItemBase):
    pass


class PayoutItemResponse(PayoutItemBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: int
    ai_flags: dict[str, Any] | None = None
    policy_decision: PolicyDecision | None = None
    policy_reasons: dict[str, Any] | None = None
    human_decision: HumanDecision
    paypal_item_status: PayPalItemStatus
    paypal_item_id: str | None = None
    created_at: datetime
    updated_at: datetime


class PayoutItemDecision(BaseModel):
    human_decision: HumanDecision


class PayeeBase(BaseModel):
    email: EmailStr
    name: str | None = None


class PayeeResponse(PayeeBase):
    model_config = ConfigDict(from_attributes=True)

    avg_amount: Decimal | None = None
    last_paid_at: datetime | None = None
    total_payments: int
    created_at: datetime
    updated_at: datetime


class AuditEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: int
    type: str
    detail: dict[str, Any] | None = None
    created_at: datetime


class AuditSummary(BaseModel):
    run_id: int
    run_status: RunStatus
    total_items: int
    auto_approved: int
    needs_review: int
    blocked: int
    human_approved: int
    human_rejected: int
    total_amount: Decimal
    budget_cap: Decimal | None
    paypal_batch_id: str | None
    items: list[PayoutItemResponse]
    events: list[AuditEventResponse]


class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str


class PolicyReason(BaseModel):
    code: str
    message: str
    severity: str


class PolicyResult(BaseModel):
    decision: PolicyDecision
    reasons: list[PolicyReason]


class AIFlags(BaseModel):
    duplicates: list[dict[str, Any]] = []
    unusual_amounts: list[dict[str, Any]] = []
    malformed_emails: list[dict[str, Any]] = []
    over_budget: list[dict[str, Any]] = []
    unknown_payees: list[dict[str, Any]] = []


class ParsedPayee(BaseModel):
    name: str
    email: str = ""
    amount: Decimal
    currency: str = "USD"
    note: str | None = None


class ParsedPayouts(BaseModel):
    payees: list[ParsedPayee]
    raw_input_summary: str


class AIFlag(BaseModel):
    type: str
    message: str


class AIReviewItem(BaseModel):
    email: str
    flags: list[AIFlag] = []
    explanation: str


class AIReviewResponse(BaseModel):
    items: list[AIReviewItem]
    audit_summary: str
