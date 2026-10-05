#!/usr/bin/env python
"""
Test script to run AI parser and reviewer on sample data.
This uses mocked LLM responses for demonstration.
"""
import json
from decimal import Decimal
from unittest.mock import MagicMock, patch

from app.services.ai_parser import AIParser
from app.services.ai_review import AIReviewer
from app.services.policy import PolicyConfig, evaluate_batch


def create_mock_parser_response():
    """Mock response for the sample CSV data."""
    return MagicMock(
        content=[MagicMock(text=json.dumps([
            {"name": "Amina Diallo", "email": "amina.diallo@example.com", "amount": "480.00", "currency": "USD", "note": "40 hrs at $12/hr"},
            {"name": "Brian O'Connor", "email": "brian.oconnor@example.com", "amount": "300.00", "currency": "USD", "note": "flat fee"},
            {"name": "Carlos Mendez", "email": "carlos.mendez@example.com", "amount": "1250.00", "currency": "USD", "note": "project completion"},
            {"name": "Amina Diallo", "email": "amina.diallo@example.com", "amount": "480.00", "currency": "USD", "note": "duplicate entry"},
            {"name": "Diana Prince", "email": "diana.prince@invalid-email", "amount": "200.00", "currency": "USD", "note": "malformed email"},
            {"name": "Ethan Hunt", "email": "ethan.hunt@example.com", "amount": "5000.00", "currency": "USD", "note": "unusually large"},
            {"name": "Fiona Gallagher", "email": "fiona.g@example.com", "amount": "50.00", "currency": "USD", "note": "small payment"},
            {"name": "Grace Hopper", "email": "grace.hopper@example.com", "amount": "480.00", "currency": "USD", "note": "40 hrs at $12/hr"},
        ]))]
    )


def create_mock_review_response():
    """Mock response for the review."""
    return MagicMock(
        content=[MagicMock(text=json.dumps({
            "items": [
                {"email": "amina.diallo@example.com", "flags": [{"type": "duplicate", "message": "Duplicate payee in this run"}], "explanation": "Flagged as duplicate entry in this run"},
                {"email": "brian.oconnor@example.com", "flags": [], "explanation": "No issues detected"},
                {"email": "carlos.mendez@example.com", "flags": [], "explanation": "No issues detected"},
                {"email": "amina.diallo@example.com", "flags": [{"type": "duplicate", "message": "Duplicate payee in this run"}], "explanation": "Flagged as duplicate entry in this run"},
                {"email": "diana.prince@invalid-email", "flags": [{"type": "invalid_email", "message": "Invalid email format: diana.prince@invalid-email"}], "explanation": "Invalid email format"},
                {"email": "ethan.hunt@example.com", "flags": [{"type": "anomaly", "message": "Amount $5000.00 is unusual vs average $100.00"}], "explanation": "Unusually large payment"},
                {"email": "fiona.g@example.com", "flags": [], "explanation": "No issues detected"},
                {"email": "grace.hopper@example.com", "flags": [], "explanation": "No issues detected"},
            ],
            "audit_summary": "Run contains 8 payments totaling $8240.00. 5 auto-approved, 3 need review (2 duplicates, 1 invalid email, 1 anomaly). Budget cap: $10000.00."
        }))]
    )


def run_demo():
    print("=" * 60)
    print("SafePayout AI Demo - Sample Data Processing")
    print("=" * 60)

    # Load sample CSV
    with open("sample_data/messy_payouts.csv") as f:
        csv_content = f.read()

    print("\n1. Parsing CSV with AI...")
    print("-" * 40)

    with patch("app.services.ai_parser.anthropic.Anthropic") as mock_client_class:
        mock_client = MagicMock()
        mock_client.messages.create.return_value = create_mock_parser_response()
        mock_client_class.return_value = mock_client

        parser = AIParser(client=mock_client)
        parsed = parser.parse(csv_content, is_csv=True)

        print(f"Parsed {len(parsed.payees)} payees:")
        for i, p in enumerate(parsed.payees, 1):
            print(f"  {i}. {p.name} <{p.email}> ${p.amount:.2f} {p.currency} - {p.note}")

    print("\n2. Running Policy Engine...")
    print("-" * 40)

    config = PolicyConfig(
        per_payee_cap=Decimal("1000"),
        total_run_cap=Decimal("10000"),
        anomaly_multiplier=Decimal("3"),
        duplicate_within_days=30,
    )

    items = [
        {"name": p.name, "email": p.email, "amount": str(p.amount), "currency": p.currency, "note": p.note}
        for p in parsed.payees
    ]

    # Mock payee history for anomaly detection
    payee_histories = {
        "amina.diallo@example.com": {"avg_amount": Decimal("480"), "total_payments": 3},
        "brian.oconnor@example.com": {"avg_amount": Decimal("300"), "total_payments": 2},
        "carlos.mendez@example.com": {"avg_amount": Decimal("1250"), "total_payments": 1},
        "ethan.hunt@example.com": {"avg_amount": Decimal("100"), "total_payments": 1},
        "fiona.g@example.com": {"avg_amount": Decimal("50"), "total_payments": 1},
        "grace.hopper@example.com": {"avg_amount": Decimal("480"), "total_payments": 2},
    }

    policy_results = evaluate_batch(
        items=items,
        config=config,
        payee_histories=payee_histories,
        budget_cap=Decimal("10000"),
    )

    for i, (item, result) in enumerate(zip(items, policy_results, strict=True), 1):
        status = result.decision.value
        reasons = [r.code.value for r in result.reasons] if result.reasons else ["OK"]
        print(f"  {i}. {item['email']}: {status} - {', '.join(reasons)}")

    print("\n3. AI Review (flags & explanations)...")
    print("-" * 40)

    with patch("app.services.ai_review.anthropic.Anthropic") as mock_client_class:
        mock_client = MagicMock()
        mock_client.messages.create.return_value = create_mock_review_response()
        mock_client_class.return_value = mock_client

        reviewer = AIReviewer(client=mock_client)
        review = reviewer.review(parsed.payees, policy_results, payee_histories, Decimal("10000"))

        print(f"\nAudit Summary: {review.audit_summary}")
        print("\nPer-item flags:")
        for item in review.items:
            flags_str = ", ".join(f"[{f.type}] {f.message}" for f in item.flags) if item.flags else "No flags"
            print(f"  {item.email}: {flags_str}")
            if item.explanation and item.flags:
                print(f"    Explanation: {item.explanation}")

    print("\n" + "=" * 60)
    print("Demo complete!")
    print("=" * 60)


if __name__ == "__main__":
    run_demo()
