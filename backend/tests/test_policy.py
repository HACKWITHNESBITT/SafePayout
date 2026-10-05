from decimal import Decimal

import pytest
from app.services.policy import (
    PolicyConfig,
    PolicyDecision,
    PolicyReasonCode,
    PolicyReasonSeverity,
    check_allowlisted,
    check_amount_bounds,
    check_anomaly,
    check_duplicate_in_run,
    check_email_format,
    check_per_payee_cap,
    check_recent_duplicate,
    check_total_budget,
    evaluate_batch,
    evaluate_item,
    normalize_email,
    validate_email,
)


class TestEmailValidation:
    def test_valid_emails(self):
        assert validate_email("user@example.com")
        assert validate_email("user.name@example.com")
        assert validate_email("user+tag@example.co.uk")
        assert validate_email("user123@sub.domain.com")

    def test_invalid_emails(self):
        assert not validate_email("invalid")
        assert not validate_email("user@")
        assert not validate_email("@example.com")
        assert not validate_email("user@.com")
        assert not validate_email("user@com")
        assert not validate_email("")

    def test_normalize_email(self):
        assert normalize_email("USER@EXAMPLE.COM") == "user@example.com"
        assert normalize_email("  User@Example.Com  ") == "user@example.com"
        assert normalize_email("user+tag@example.com") == "user+tag@example.com"

    def test_check_email_format_valid(self):
        assert check_email_format("user@example.com") is None

    def test_check_email_format_invalid(self):
        reason = check_email_format("invalid")
        assert reason is not None
        assert reason.code == PolicyReasonCode.INVALID_EMAIL_FORMAT
        assert reason.severity == PolicyReasonSeverity.ERROR


class TestAllowlist:
    def test_no_allowlist_allows_all(self):
        config = PolicyConfig.default()
        assert check_allowlisted("anyone@anywhere.com", config.allowlisted_domains, config.allowlisted_emails) is None

    def test_allowlisted_domain(self):
        config = PolicyConfig(allowlisted_domains=["example.com", "company.com"])
        assert check_allowlisted("user@example.com", config.allowlisted_domains, config.allowlisted_emails) is None
        assert check_allowlisted("user@EXAMPLE.COM", config.allowlisted_domains, config.allowlisted_emails) is None

    def test_allowlisted_email(self):
        config = PolicyConfig(allowlisted_emails=["boss@company.com"])
        assert check_allowlisted("boss@company.com", config.allowlisted_domains, config.allowlisted_emails) is None
        assert check_allowlisted("BOSS@COMPANY.COM", config.allowlisted_domains, config.allowlisted_emails) is None

    def test_not_allowlisted(self):
        config = PolicyConfig(allowlisted_domains=["example.com"])
        reason = check_allowlisted("user@other.com", config.allowlisted_domains, config.allowlisted_emails)
        assert reason is not None
        assert reason.code == PolicyReasonCode.PAYEE_NOT_ALLOWLISTED
        assert reason.severity == PolicyReasonSeverity.WARNING


class TestPerPayeeCap:
    def test_within_cap(self):
        assert check_per_payee_cap(Decimal("100"), Decimal("500"), "user@example.com") is None

    def test_exceeds_cap(self):
        reason = check_per_payee_cap(Decimal("600"), Decimal("500"), "user@example.com")
        assert reason is not None
        assert reason.code == PolicyReasonCode.AMOUNT_EXCEEDS_PAYEE_CAP
        assert reason.severity == PolicyReasonSeverity.ERROR

    def test_no_cap(self):
        assert check_per_payee_cap(Decimal("10000"), None, "user@example.com") is None


class TestAmountBounds:
    def test_within_bounds(self):
        assert check_amount_bounds(Decimal("100"), Decimal("1"), Decimal("1000"), "user@example.com") is None

    def test_below_minimum(self):
        reason = check_amount_bounds(Decimal("0"), Decimal("0.01"), None, "user@example.com")
        assert reason is not None
        assert reason.severity == PolicyReasonSeverity.ERROR

    def test_above_maximum(self):
        reason = check_amount_bounds(Decimal("2000"), Decimal("1"), Decimal("1000"), "user@example.com")
        assert reason is not None
        assert reason.severity == PolicyReasonSeverity.ERROR


class TestAnomalyDetection:
    def test_within_multiplier(self):
        assert check_anomaly(Decimal("200"), Decimal("100"), Decimal("3"), "user@example.com") is None

    def test_exceeds_multiplier(self):
        reason = check_anomaly(Decimal("500"), Decimal("100"), Decimal("3"), "user@example.com")
        assert reason is not None
        assert reason.code == PolicyReasonCode.AMOUNT_ANOMALY
        assert reason.severity == PolicyReasonSeverity.WARNING

    def test_no_history(self):
        assert check_anomaly(Decimal("500"), None, Decimal("3"), "user@example.com") is None

    def test_zero_average(self):
        assert check_anomaly(Decimal("500"), Decimal("0"), Decimal("3"), "user@example.com") is None


class TestDuplicateInRun:
    def test_first_occurrence(self):
        seen = set()
        assert check_duplicate_in_run("user@example.com", seen) is None
        # Function only checks, doesn't add - caller must add

    def test_duplicate_same_case(self):
        seen = {"user@example.com"}
        reason = check_duplicate_in_run("user@example.com", seen)
        assert reason is not None
        assert reason.code == PolicyReasonCode.DUPLICATE_PAYEE_IN_RUN
        assert reason.severity == PolicyReasonSeverity.ERROR

    def test_duplicate_different_case(self):
        seen = {"user@example.com"}
        reason = check_duplicate_in_run("USER@EXAMPLE.COM", seen)
        assert reason is not None
        assert reason.code == PolicyReasonCode.DUPLICATE_PAYEE_IN_RUN


class TestRecentDuplicate:
    def test_no_recent_payments(self):
        assert check_recent_duplicate("user@example.com", Decimal("100"), "USD", [], 30) is None

    def test_exact_duplicate(self):
        recent = [{"email": "user@example.com", "amount": Decimal("100"), "currency": "USD"}]
        reason = check_recent_duplicate("user@example.com", Decimal("100"), "USD", recent, 30)
        assert reason is not None
        assert reason.code == PolicyReasonCode.DUPLICATE_PAYMENT_RECENT
        assert reason.severity == PolicyReasonSeverity.WARNING

    def test_different_amount(self):
        recent = [{"email": "user@example.com", "amount": Decimal("100"), "currency": "USD"}]
        assert check_recent_duplicate("user@example.com", Decimal("200"), "USD", recent, 30) is None

    def test_different_currency(self):
        recent = [{"email": "user@example.com", "amount": Decimal("100"), "currency": "USD"}]
        assert check_recent_duplicate("user@example.com", Decimal("100"), "EUR", recent, 30) is None

    def test_case_insensitive_email(self):
        recent = [{"email": "USER@EXAMPLE.COM", "amount": Decimal("100"), "currency": "USD"}]
        reason = check_recent_duplicate("user@example.com", Decimal("100"), "USD", recent, 30)
        assert reason is not None


class TestTotalBudget:
    def test_within_budget(self):
        assert check_total_budget(Decimal("1000"), Decimal("5000")) is None

    def test_exceeds_budget(self):
        reason = check_total_budget(Decimal("6000"), Decimal("5000"))
        assert reason is not None
        assert reason.code == PolicyReasonCode.TOTAL_EXCEEDS_BUDGET
        assert reason.severity == PolicyReasonSeverity.ERROR

    def test_no_budget_cap(self):
        assert check_total_budget(Decimal("100000"), None) is None


class TestEvaluateItem:
    def test_auto_approved_clean_item(self):
        config = PolicyConfig.default()
        item = {"name": "John", "email": "john@example.com", "amount": "100", "currency": "USD"}
        result = evaluate_item(item, config)
        assert result.decision == PolicyDecision.AUTO_APPROVED
        assert len(result.reasons) == 0

    def test_blocked_invalid_email(self):
        config = PolicyConfig.default()
        item = {"name": "John", "email": "invalid", "amount": "100", "currency": "USD"}
        result = evaluate_item(item, config)
        assert result.decision == PolicyDecision.BLOCKED
        assert any(r.code == PolicyReasonCode.INVALID_EMAIL_FORMAT for r in result.reasons)

    def test_blocked_exceeds_payee_cap(self):
        config = PolicyConfig(per_payee_cap=Decimal("500"))
        item = {"name": "John", "email": "john@example.com", "amount": "600", "currency": "USD"}
        result = evaluate_item(item, config)
        assert result.decision == PolicyDecision.BLOCKED
        assert any(r.code == PolicyReasonCode.AMOUNT_EXCEEDS_PAYEE_CAP for r in result.reasons)

    def test_needs_review_anomaly(self):
        config = PolicyConfig(anomaly_multiplier=Decimal("2"))
        item = {"name": "John", "email": "john@example.com", "amount": "500", "currency": "USD"}
        history = {"avg_amount": Decimal("100")}
        result = evaluate_item(item, config, payee_history=history)
        assert result.decision == PolicyDecision.NEEDS_REVIEW
        assert any(r.code == PolicyReasonCode.AMOUNT_ANOMALY for r in result.reasons)

    def test_needs_review_not_allowlisted(self):
        config = PolicyConfig(allowlisted_domains=["company.com"])
        item = {"name": "John", "email": "john@other.com", "amount": "100", "currency": "USD"}
        result = evaluate_item(item, config)
        assert result.decision == PolicyDecision.NEEDS_REVIEW
        assert any(r.code == PolicyReasonCode.PAYEE_NOT_ALLOWLISTED for r in result.reasons)

    def test_decimal_precision(self):
        config = PolicyConfig.default()
        item = {"name": "John", "email": "john@example.com", "amount": "100.005", "currency": "USD"}
        result = evaluate_item(item, config)
        assert result.decision == PolicyDecision.AUTO_APPROVED

    def test_multiple_errors_blocked(self):
        config = PolicyConfig(per_payee_cap=Decimal("500"), allowlisted_domains=["company.com"])
        item = {"name": "John", "email": "invalid", "amount": "600", "currency": "USD"}
        result = evaluate_item(item, config)
        assert result.decision == PolicyDecision.BLOCKED
        error_count = sum(1 for r in result.reasons if r.severity == PolicyReasonSeverity.ERROR)
        assert error_count >= 2


class TestEvaluateBatch:
    def test_all_auto_approved(self):
        config = PolicyConfig.default()
        items = [
            {"name": "John", "email": "john@example.com", "amount": "100", "currency": "USD"},
            {"name": "Jane", "email": "jane@example.com", "amount": "200", "currency": "USD"},
        ]
        results = evaluate_batch(items, config)
        assert all(r.decision == PolicyDecision.AUTO_APPROVED for r in results)

    def test_duplicate_in_run_blocked(self):
        config = PolicyConfig.default()
        items = [
            {"name": "John", "email": "john@example.com", "amount": "100", "currency": "USD"},
            {"name": "John Again", "email": "JOHN@EXAMPLE.COM", "amount": "200", "currency": "USD"},
        ]
        results = evaluate_batch(items, config)
        assert results[0].decision == PolicyDecision.AUTO_APPROVED
        assert results[1].decision == PolicyDecision.BLOCKED
        assert any(r.code == PolicyReasonCode.DUPLICATE_PAYEE_IN_RUN for r in results[1].reasons)

    def test_recent_duplicate_flagged(self):
        config = PolicyConfig.default()
        recent = [{"email": "john@example.com", "amount": Decimal("100"), "currency": "USD"}]
        items = [
            {"name": "John", "email": "john@example.com", "amount": "100", "currency": "USD"},
        ]
        results = evaluate_batch(items, config, recent_payments=recent)
        assert results[0].decision == PolicyDecision.NEEDS_REVIEW
        assert any(r.code == PolicyReasonCode.DUPLICATE_PAYMENT_RECENT for r in results[0].reasons)

    def test_batch_budget_enforced(self):
        config = PolicyConfig(total_run_cap=Decimal("500"))
        items = [
            {"name": "John", "email": "john@example.com", "amount": "300", "currency": "USD"},
            {"name": "Jane", "email": "jane@example.com", "amount": "300", "currency": "USD"},
        ]
        results = evaluate_batch(items, config)
        assert results[0].decision == PolicyDecision.AUTO_APPROVED
        assert results[1].decision == PolicyDecision.BLOCKED
        assert any(r.code == PolicyReasonCode.TOTAL_EXCEEDS_BUDGET for r in results[1].reasons)

    def test_budget_cap_from_run_overrides_config(self):
        config = PolicyConfig(total_run_cap=Decimal("1000"))
        items = [
            {"name": "John", "email": "john@example.com", "amount": "600", "currency": "USD"},
            {"name": "Jane", "email": "jane@example.com", "amount": "600", "currency": "USD"},
        ]
        results = evaluate_batch(items, config, budget_cap=Decimal("1000"))
        assert results[0].decision == PolicyDecision.AUTO_APPROVED
        assert results[1].decision == PolicyDecision.BLOCKED

    def test_payee_history_lookup(self):
        config = PolicyConfig(anomaly_multiplier=Decimal("2"))
        histories = {
            "john@example.com": {"avg_amount": Decimal("100")},
        }
        items = [
            {"name": "John", "email": "john@example.com", "amount": "500", "currency": "USD"},
        ]
        results = evaluate_batch(items, config, payee_histories=histories)
        assert results[0].decision == PolicyDecision.NEEDS_REVIEW
        assert any(r.code == PolicyReasonCode.AMOUNT_ANOMALY for r in results[0].reasons)

    def test_empty_batch(self):
        config = PolicyConfig.default()
        results = evaluate_batch([], config)
        assert results == []


class TestPolicyConfig:
    def test_default_config(self):
        config = PolicyConfig.default()
        assert config.per_payee_cap is None
        assert config.total_run_cap is None
        assert config.duplicate_within_days == 30
        assert config.anomaly_multiplier == Decimal("3")

    def test_strict_config(self):
        config = PolicyConfig.strict()
        assert config.per_payee_cap == Decimal("5000")
        assert config.total_run_cap == Decimal("50000")
        assert config.duplicate_within_days == 30
        assert "example.com" in config.allowlisted_domains
        assert config.anomaly_multiplier == Decimal("2")
        assert config.max_amount == Decimal("10000")

    def test_frozen_config(self):
        config = PolicyConfig.default()
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            config.per_payee_cap = Decimal("1000")


class TestEdgeCases:
    def test_amount_as_string(self):
        config = PolicyConfig.default()
        item = {"name": "John", "email": "john@example.com", "amount": "100.50", "currency": "USD"}
        result = evaluate_item(item, config)
        assert result.decision == PolicyDecision.AUTO_APPROVED

    def test_amount_as_decimal(self):
        config = PolicyConfig.default()
        item = {"name": "John", "email": "john@example.com", "amount": Decimal("100.50"), "currency": "USD"}
        result = evaluate_item(item, config)
        assert result.decision == PolicyDecision.AUTO_APPROVED

    def test_amount_as_int(self):
        config = PolicyConfig.default()
        item = {"name": "John", "email": "john@example.com", "amount": 100, "currency": "USD"}
        result = evaluate_item(item, config)
        assert result.decision == PolicyDecision.AUTO_APPROVED

    def test_zero_amount_blocked(self):
        config = PolicyConfig(min_amount=Decimal("0.01"))
        item = {"name": "John", "email": "john@example.com", "amount": "0", "currency": "USD"}
        result = evaluate_item(item, config)
        assert result.decision == PolicyDecision.BLOCKED

    def test_negative_amount_blocked(self):
        config = PolicyConfig(min_amount=Decimal("0.01"))
        item = {"name": "John", "email": "john@example.com", "amount": "-10", "currency": "USD"}
        result = evaluate_item(item, config)
        assert result.decision == PolicyDecision.BLOCKED

    def test_missing_email_blocked(self):
        config = PolicyConfig.default()
        item = {"name": "John", "amount": "100", "currency": "USD"}
        result = evaluate_item(item, config)
        assert result.decision == PolicyDecision.BLOCKED

    def test_missing_amount_defaults_to_zero(self):
        config = PolicyConfig(min_amount=Decimal("0.01"))
        item = {"name": "John", "email": "john@example.com", "currency": "USD"}
        result = evaluate_item(item, config)
        assert result.decision == PolicyDecision.BLOCKED

    def test_unicode_email(self):
        assert validate_email("用户@例子.中国") is False
        reason = check_email_format("用户@例子.中国")
        assert reason is not None
        assert reason.code == PolicyReasonCode.INVALID_EMAIL_FORMAT
