from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


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


class PayoutRun(Base):
    __tablename__ = "payout_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    status: Mapped[RunStatus] = mapped_column(
        Enum(RunStatus), default=RunStatus.DRAFT, nullable=False
    )
    budget_cap: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    sender_batch_id: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    paypal_batch_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)

    items: Mapped[list["PayoutItem"]] = relationship(
        "PayoutItem", back_populates="run", cascade="all, delete-orphan"
    )
    audit_events: Mapped[list["AuditEvent"]] = relationship(
        "AuditEvent", back_populates="run", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<PayoutRun(id={self.id}, status={self.status.value}, sender_batch_id={self.sender_batch_id})>"


class PayoutItem(Base):
    __tablename__ = "payout_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("payout_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_flags: Mapped[dict | None] = mapped_column(SQLiteJSON, nullable=True)
    policy_decision: Mapped[PolicyDecision | None] = mapped_column(
        Enum(PolicyDecision), nullable=True
    )
    policy_reasons: Mapped[dict | None] = mapped_column(SQLiteJSON, nullable=True)
    human_decision: Mapped[HumanDecision] = mapped_column(
        Enum(HumanDecision), default=HumanDecision.PENDING, nullable=False
    )
    paypal_item_status: Mapped[PayPalItemStatus] = mapped_column(
        Enum(PayPalItemStatus), default=PayPalItemStatus.PENDING, nullable=False
    )
    paypal_item_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    run: Mapped["PayoutRun"] = relationship("PayoutRun", back_populates="items")

    __table_args__ = (
        Index("ix_payout_items_run_email", "run_id", "email"),
    )

    def __repr__(self) -> str:
        return f"<PayoutItem(id={self.id}, run_id={self.run_id}, email={self.email}, amount={self.amount})>"


class Payee(Base):
    __tablename__ = "payees"

    email: Mapped[str] = mapped_column(String(255), primary_key=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    avg_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    last_paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    total_payments: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<Payee(email={self.email}, name={self.name}, avg_amount={self.avg_amount})>"


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("payout_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String(100), nullable=False)
    detail: Mapped[dict | None] = mapped_column(SQLiteJSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    run: Mapped["PayoutRun"] = relationship("PayoutRun", back_populates="audit_events")

    def __repr__(self) -> str:
        return f"<AuditEvent(id={self.id}, run_id={self.run_id}, type={self.type})>"
