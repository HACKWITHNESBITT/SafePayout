from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class PolicyDecision(StrEnum):
    AUTO_APPROVED = "AUTO_APPROVED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    BLOCKED = "BLOCKED"


class PolicyReasonCode(StrEnum):
    AMOUNT_EXCEEDS_PAYEE_CAP = "AMOUNT_EXCEEDS_PAYEE_CAP"
    AMOUNT_EXCEEDS_RUN_CAP = "AMOUNT_EXCEEDS_RUN_CAP"
    DUPLICATE_PAYEE_IN_RUN = "DUPLICATE_PAYEE_IN_RUN"
    DUPLICATE_PAYMENT_RECENT = "DUPLICATE_PAYMENT_RECENT"
    INVALID_EMAIL_FORMAT = "INVALID_EMAIL_FORMAT"
    PAYEE_NOT_ALLOWLISTED = "PAYEE_NOT_ALLOWLISTED"
    AMOUNT_ANOMALY = "AMOUNT_ANOMALY"
    TOTAL_EXCEEDS_BUDGET = "TOTAL_EXCEEDS_BUDGET"


class PolicyReasonSeverity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


@dataclass
class PolicyReason:
    code: PolicyReasonCode
    message: str
    severity: PolicyReasonSeverity
    details: dict = field(default_factory=dict)


@dataclass
class PolicyResult:
    decision: PolicyDecision
    reasons: list[PolicyReason]

    def is_blocked(self) -> bool:
        return self.decision == PolicyDecision.BLOCKED

    def needs_review(self) -> bool:
        return self.decision == PolicyDecision.NEEDS_REVIEW

    def is_auto_approved(self) -> bool:
        return self.decision == PolicyDecision.AUTO_APPROVED


class PolicyConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    per_payee_cap: Decimal | None = Field(default=None, ge=0)
    total_run_cap: Decimal | None = Field(default=None, ge=0)
    duplicate_within_days: int = Field(default=30, ge=0)
    allowlisted_domains: list[str] = Field(default_factory=list)
    allowlisted_emails: list[str] = Field(default_factory=list)
    anomaly_multiplier: Decimal = Field(default=Decimal("3"), gt=0)
    min_amount: Decimal = Field(default=Decimal("0.01"), ge=0)
    max_amount: Decimal | None = Field(default=None, ge=0)

    @classmethod
    def default(cls) -> "PolicyConfig":
        return cls()

    @classmethod
    def strict(cls) -> "PolicyConfig":
        return cls(
            per_payee_cap=Decimal("5000"),
            total_run_cap=Decimal("50000"),
            duplicate_within_days=30,
            allowlisted_domains=["example.com", "company.com"],
            anomaly_multiplier=Decimal("2"),
            max_amount=Decimal("10000"),
        )


def validate_email(email: str) -> bool:
    import re
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))


def normalize_email(email: str) -> str:
    return email.strip().lower()


def check_email_format(email: str) -> PolicyReason | None:
    if not validate_email(email):
        return PolicyReason(
            code=PolicyReasonCode.INVALID_EMAIL_FORMAT,
            message=f"Invalid email format: {email}",
            severity=PolicyReasonSeverity.ERROR,
            details={"email": email},
        )
    return None


def check_allowlisted(
    email: str,
    allowlisted_domains: list[str],
    allowlisted_emails: list[str],
) -> PolicyReason | None:
    normalized = normalize_email(email)
    if normalized in [normalize_email(e) for e in allowlisted_emails]:
        return None
    domain = normalized.split("@")[-1]
    if domain in [d.lower() for d in allowlisted_domains]:
        return None
    if not allowlisted_domains and not allowlisted_emails:
        return None
    return PolicyReason(
        code=PolicyReasonCode.PAYEE_NOT_ALLOWLISTED,
        message=f"Payee not in allowlist: {email}",
        severity=PolicyReasonSeverity.WARNING,
        details={"email": email, "domain": domain},
    )


def check_per_payee_cap(
    amount: Decimal,
    cap: Decimal | None,
    email: str,
) -> PolicyReason | None:
    if cap is not None and amount > cap:
        return PolicyReason(
            code=PolicyReasonCode.AMOUNT_EXCEEDS_PAYEE_CAP,
            message=f"Amount {amount} exceeds per-payee cap of {cap}",
            severity=PolicyReasonSeverity.ERROR,
            details={"amount": str(amount), "cap": str(cap), "email": email},
        )
    return None


def check_amount_bounds(
    amount: Decimal,
    min_amount: Decimal,
    max_amount: Decimal | None,
    email: str,
) -> PolicyReason | None:
    if amount < min_amount:
        return PolicyReason(
            code=PolicyReasonCode.AMOUNT_EXCEEDS_PAYEE_CAP,
            message=f"Amount {amount} below minimum {min_amount}",
            severity=PolicyReasonSeverity.ERROR,
            details={"amount": str(amount), "min": str(min_amount), "email": email},
        )
    if max_amount is not None and amount > max_amount:
        return PolicyReason(
            code=PolicyReasonCode.AMOUNT_EXCEEDS_PAYEE_CAP,
            message=f"Amount {amount} exceeds maximum {max_amount}",
            severity=PolicyReasonSeverity.ERROR,
            details={"amount": str(amount), "max": str(max_amount), "email": email},
        )
    return None


def check_anomaly(
    amount: Decimal,
    avg_amount: Decimal | None,
    multiplier: Decimal,
    email: str,
) -> PolicyReason | None:
    if avg_amount is not None and avg_amount > 0:
        threshold = avg_amount * multiplier
        if amount > threshold:
            return PolicyReason(
                code=PolicyReasonCode.AMOUNT_ANOMALY,
                message=f"Amount {amount} is {multiplier}x payee average {avg_amount}",
                severity=PolicyReasonSeverity.WARNING,
                details={
                    "amount": str(amount),
                    "avg_amount": str(avg_amount),
                    "threshold": str(threshold),
                    "multiplier": str(multiplier),
                    "email": email,
                },
            )
    return None


def check_duplicate_in_run(
    email: str,
    seen_emails: set[str],
) -> PolicyReason | None:
    normalized = normalize_email(email)
    if normalized in seen_emails:
        return PolicyReason(
            code=PolicyReasonCode.DUPLICATE_PAYEE_IN_RUN,
            message=f"Duplicate payee in this run: {email}",
            severity=PolicyReasonSeverity.ERROR,
            details={"email": email},
        )
    return None


def check_recent_duplicate(
    email: str,
    amount: Decimal,
    currency: str,
    recent_payments: list[dict],
    within_days: int,
) -> PolicyReason | None:
    normalized = normalize_email(email)
    for payment in recent_payments:
        if (
            normalize_email(payment.get("email", "")) == normalized
            and payment.get("amount") == amount
            and payment.get("currency") == currency
        ):
            return PolicyReason(
                code=PolicyReasonCode.DUPLICATE_PAYMENT_RECENT,
                message=f"Duplicate payment to {email} within {within_days} days",
                severity=PolicyReasonSeverity.WARNING,
                details={
                    "email": email,
                    "amount": str(amount),
                    "currency": currency,
                    "within_days": within_days,
                },
            )
    return None


def check_total_budget(
    total_amount: Decimal,
    budget_cap: Decimal | None,
) -> PolicyReason | None:
    if budget_cap is not None and total_amount > budget_cap:
        return PolicyReason(
            code=PolicyReasonCode.TOTAL_EXCEEDS_BUDGET,
            message=f"Total run amount {total_amount} exceeds budget cap {budget_cap}",
            severity=PolicyReasonSeverity.ERROR,
            details={"total_amount": str(total_amount), "budget_cap": str(budget_cap)},
        )
    return None


def evaluate_item(
    item: dict,
    config: PolicyConfig,
    payee_history: dict | None = None,
    seen_emails: set[str] | None = None,
    recent_payments: list[dict] | None = None,
    run_total: Decimal | None = None,
) -> PolicyResult:
    """
    Evaluate a single payout item against all policy rules.

    Args:
        item: Dict with keys: name, email, amount, currency, note
        config: PolicyConfig with all rule thresholds
        payee_history: Optional dict with avg_amount, last_paid_at, total_payments
        seen_emails: Set of normalized emails already seen in this run
        recent_payments: List of recent payment dicts for duplicate check
        run_total: Current running total of the batch (for budget check)

    Returns:
        PolicyResult with decision and reasons
    """
    reasons: list[PolicyReason] = []
    email = item.get("email", "")
    amount = Decimal(str(item.get("amount", "0")))
    currency = item.get("currency", "USD")

    seen_emails = seen_emails or set()
    recent_payments = recent_payments or []
    payee_history = payee_history or {}

    if reason := check_email_format(email):
        reasons.append(reason)

    if reason := check_allowlisted(email, config.allowlisted_domains, config.allowlisted_emails):
        reasons.append(reason)

    if reason := check_per_payee_cap(amount, config.per_payee_cap, email):
        reasons.append(reason)

    if reason := check_amount_bounds(amount, config.min_amount, config.max_amount, email):
        reasons.append(reason)

    avg_amount = payee_history.get("avg_amount")
    if avg_amount is not None:
        avg_amount = Decimal(str(avg_amount))
    if reason := check_anomaly(amount, avg_amount, config.anomaly_multiplier, email):
        reasons.append(reason)

    if reason := check_duplicate_in_run(email, seen_emails):
        reasons.append(reason)

    if reason := check_recent_duplicate(email, amount, currency, recent_payments, config.duplicate_within_days):
        reasons.append(reason)

    if run_total is not None:
        projected_total = run_total + amount
        if reason := check_total_budget(projected_total, config.total_run_cap):
            reasons.append(reason)

    has_errors = any(r.severity == PolicyReasonSeverity.ERROR for r in reasons)
    has_warnings = any(r.severity == PolicyReasonSeverity.WARNING for r in reasons)

    if has_errors:
        decision = PolicyDecision.BLOCKED
    elif has_warnings:
        decision = PolicyDecision.NEEDS_REVIEW
    else:
        decision = PolicyDecision.AUTO_APPROVED

    return PolicyResult(decision=decision, reasons=reasons)


def evaluate_batch(
    items: list[dict],
    config: PolicyConfig,
    payee_histories: dict[str, dict] | None = None,
    recent_payments: list[dict] | None = None,
    budget_cap: Decimal | None = None,
) -> list[PolicyResult]:
    """
    Evaluate a batch of payout items, checking cross-item rules like duplicates and total budget.

    Args:
        items: List of item dicts
        config: PolicyConfig
        payee_histories: Dict mapping email -> payee history
        recent_payments: List of recent payments for duplicate detection
        budget_cap: Override total run cap (e.g., from PayoutRun.budget_cap)

    Returns:
        List of PolicyResult in same order as items
    """
    results = []
    seen_emails: set[str] = set()
    running_total = Decimal("0")

    for item in items:
        email = normalize_email(item.get("email", ""))
        payee_history = payee_histories.get(email) if payee_histories else None

        result = evaluate_item(
            item=item,
            config=config,
            payee_history=payee_history,
            seen_emails=seen_emails,
            recent_payments=recent_payments,
            run_total=running_total,
        )

        if result.is_auto_approved() or result.needs_review():
            running_total += Decimal(str(item.get("amount", "0")))
            seen_emails.add(email)

        results.append(result)

    return results
