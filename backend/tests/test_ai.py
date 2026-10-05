import json
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from app.schemas import AIReviewResponse, ParsedPayee, ParsedPayouts
from app.services.ai_parser import AIParser, parse_payouts
from app.services.ai_review import AIReviewer, review_payouts
from app.services.policy import (
    PolicyDecision,
    PolicyReason,
    PolicyReasonCode,
    PolicyReasonSeverity,
    PolicyResult,
)


class MockAnthropicResponse:
    def __init__(self, text: str):
        self.content = [MagicMock(text=text)]


class TestAIParser:
    def test_parse_csv_success(self):
        mock_response = MockAnthropicResponse(json.dumps([
            {"name": "Amina", "email": "amina@example.com", "amount": "480.00", "currency": "USD", "note": "40 hrs at $12"},
            {"name": "Brian", "email": "brian@example.com", "amount": "300.00", "currency": "USD", "note": "flat fee"},
        ]))

        with patch("app.services.ai_parser.anthropic.Anthropic") as mock_client_class:
            mock_client = MagicMock()
            mock_client.messages.create.return_value = mock_response
            mock_client_class.return_value = mock_client

            parser = AIParser(client=mock_client)
            result = parser.parse("name,email,amount\nAmina,amina@example.com,480", is_csv=True)

            assert isinstance(result, ParsedPayouts)
            assert len(result.payees) == 2
            assert result.payees[0].name == "Amina"
            assert result.payees[0].email == "amina@example.com"
            assert result.payees[0].amount == Decimal("480.00")
            assert result.payees[1].name == "Brian"

    def test_parse_free_text_success(self):
        mock_response = MockAnthropicResponse(json.dumps([
            {"name": "Amina", "email": "", "amount": "480.00", "currency": "USD", "note": "40 hrs at $12"},
            {"name": "Brian", "email": "", "amount": "300.00", "currency": "USD", "note": "flat $300"},
        ]))

        with patch("app.services.ai_parser.anthropic.Anthropic") as mock_client_class:
            mock_client = MagicMock()
            mock_client.messages.create.return_value = mock_response
            mock_client_class.return_value = mock_client

            parser = AIParser(client=mock_client)
            result = parser.parse("pay Amina 40 hrs at $12, Brian flat $300", is_csv=False)

            assert len(result.payees) == 2
            assert result.payees[0].name == "Amina"
            assert result.payees[0].amount == Decimal("480.00")

    def test_parse_retry_on_invalid_json(self):
        bad_response = MockAnthropicResponse("not valid json")
        good_response = MockAnthropicResponse(json.dumps([
            {"name": "Test", "email": "test@example.com", "amount": "100", "currency": "USD", "note": "test"},
        ]))

        with patch("app.services.ai_parser.anthropic.Anthropic") as mock_client_class:
            mock_client = MagicMock()
            mock_client.messages.create.side_effect = [bad_response, good_response]
            mock_client_class.return_value = mock_client

            parser = AIParser(client=mock_client)
            result = parser.parse("test input")

            assert len(result.payees) == 1
            assert mock_client.messages.create.call_count == 2

    def test_parse_fails_after_two_attempts(self):
        bad_response = MockAnthropicResponse("not valid json")

        with patch("app.services.ai_parser.anthropic.Anthropic") as mock_client_class:
            mock_client = MagicMock()
            mock_client.messages.create.return_value = bad_response
            mock_client_class.return_value = mock_client

            parser = AIParser(client=mock_client)
            with pytest.raises(ValueError, match="Failed to parse after 2 attempts"):
                parser.parse("test input")

    def test_parse_normalizes_email_to_lowercase(self):
        mock_response = MockAnthropicResponse(json.dumps([
            {"name": "Test", "email": "TEST@EXAMPLE.COM", "amount": "100", "currency": "USD", "note": "test"},
        ]))

        with patch("app.services.ai_parser.anthropic.Anthropic") as mock_client_class:
            mock_client = MagicMock()
            mock_client.messages.create.return_value = mock_response
            mock_client_class.return_value = mock_client

            parser = AIParser(client=mock_client)
            result = parser.parse("test")

            assert result.payees[0].email == "test@example.com"

    def test_parse_returns_correct_type(self):
        mock_response = MockAnthropicResponse(json.dumps([
            {"name": "Test", "email": "test@example.com", "amount": "100", "currency": "USD", "note": "test"},
        ]))

        with patch("app.services.ai_parser.anthropic.Anthropic") as mock_client_class:
            mock_client = MagicMock()
            mock_client.messages.create.return_value = mock_response
            mock_client_class.return_value = mock_client

            parser = AIParser(client=mock_client)
            result = parser.parse("test")

            assert isinstance(result, ParsedPayouts)
            assert isinstance(result.payees[0], ParsedPayee)


class TestAIReviewer:
    def test_review_success(self):
        mock_response = MockAnthropicResponse(json.dumps({
            "items": [
                {
                    "email": "amina@example.com",
                    "flags": [{"type": "duplicate", "message": "Duplicate payee in this run"}],
                    "explanation": "Flagged as duplicate"
                },
                {
                    "email": "brian@example.com",
                    "flags": [],
                    "explanation": "No issues detected"
                }
            ],
            "audit_summary": "Run contains 2 payments totaling $780.00. 1 auto-approved, 1 needs review."
        }))

        with patch("app.services.ai_review.anthropic.Anthropic") as mock_client_class:
            mock_client = MagicMock()
            mock_client.messages.create.return_value = mock_response
            mock_client_class.return_value = mock_client

            reviewer = AIReviewer(client=mock_client)
            payees = [
                ParsedPayee(name="Amina", email="amina@example.com", amount=Decimal("480"), currency="USD"),
                ParsedPayee(name="Brian", email="brian@example.com", amount=Decimal("300"), currency="USD"),
            ]
            policy_results = [
                PolicyResult(decision=PolicyDecision.NEEDS_REVIEW, reasons=[
                    PolicyReason(code=PolicyReasonCode.DUPLICATE_PAYEE_IN_RUN, message="Duplicate", severity=PolicyReasonSeverity.ERROR)
                ]),
                PolicyResult(decision=PolicyDecision.AUTO_APPROVED, reasons=[]),
            ]
            result = reviewer.review(payees, policy_results)

            assert isinstance(result, AIReviewResponse)
            assert len(result.items) == 2
            assert result.items[0].email == "amina@example.com"
            assert len(result.items[0].flags) == 1
            assert result.items[0].flags[0].type == "duplicate"
            assert result.audit_summary is not None

    def test_review_falls_back_on_llm_error(self):
        with patch("app.services.ai_review.anthropic.Anthropic") as mock_client_class:
            mock_client = MagicMock()
            mock_client.messages.create.side_effect = Exception("API error")
            mock_client_class.return_value = mock_client

            reviewer = AIReviewer(client=mock_client)
            payees = [
                ParsedPayee(name="Amina", email="amina@example.com", amount=Decimal("480"), currency="USD"),
            ]
            policy_results = [
                PolicyResult(decision=PolicyDecision.NEEDS_REVIEW, reasons=[
                    PolicyReason(code=PolicyReasonCode.DUPLICATE_PAYEE_IN_RUN, message="Duplicate", severity=PolicyReasonSeverity.ERROR)
                ]),
            ]
            result = reviewer.review(payees, policy_results)

            assert isinstance(result, AIReviewResponse)
            assert len(result.items) == 1
            assert result.items[0].email == "amina@example.com"

    def test_deterministic_review_generates_flags(self):
        reviewer = AIReviewer()
        payees = [
            ParsedPayee(name="Amina", email="amina@example.com", amount=Decimal("480"), currency="USD"),
            ParsedPayee(name="Brian", email="brian@example.com", amount=Decimal("300"), currency="USD"),
        ]
        policy_results = [
            PolicyResult(decision=PolicyDecision.NEEDS_REVIEW, reasons=[
                PolicyReason(code=PolicyReasonCode.DUPLICATE_PAYEE_IN_RUN, message="Duplicate payee", severity=PolicyReasonSeverity.ERROR)
            ]),
            PolicyResult(decision=PolicyDecision.AUTO_APPROVED, reasons=[]),
        ]
        result = reviewer._deterministic_review(payees, policy_results)

        assert "items" in result
        assert "audit_summary" in result
        assert len(result["items"]) == 2
        assert result["items"][0]["flags"][0]["type"] == "duplicate"

    def test_reason_to_flag_mapping(self):
        reviewer = AIReviewer()
        payee = ParsedPayee(name="Test", email="test@example.com", amount=Decimal("500"), currency="USD")

        reason = PolicyReason(code=PolicyReasonCode.AMOUNT_ANOMALY, message="Anomaly", severity=PolicyReasonSeverity.WARNING)
        flag = reviewer._reason_to_flag(reason, payee, Decimal("100"))
        assert flag is not None
        assert flag["type"] == "anomaly"

        reason = PolicyReason(code=PolicyReasonCode.INVALID_EMAIL_FORMAT, message="Invalid", severity=PolicyReasonSeverity.ERROR)
        flag = reviewer._reason_to_flag(reason, payee)
        assert flag is not None
        assert flag["type"] == "invalid_email"

    def test_review_with_history(self):
        mock_response = MockAnthropicResponse(json.dumps({
            "items": [{"email": "amina@example.com", "flags": [], "explanation": "OK"}],
            "audit_summary": "Test summary"
        }))

        with patch("app.services.ai_review.anthropic.Anthropic") as mock_client_class:
            mock_client = MagicMock()
            mock_client.messages.create.return_value = mock_response
            mock_client_class.return_value = mock_client

            reviewer = AIReviewer(client=mock_client)
            payees = [ParsedPayee(name="Amina", email="amina@example.com", amount=Decimal("500"), currency="USD")]
            policy_results = [PolicyResult(decision=PolicyDecision.AUTO_APPROVED, reasons=[])]
            histories = {"amina@example.com": {"avg_amount": Decimal("100"), "total_payments": 5}}

            result = reviewer.review(payees, policy_results, payee_histories=histories)
            assert isinstance(result, AIReviewResponse)


class TestConvenienceFunctions:
    def test_parse_payouts_function(self):
        mock_response = MockAnthropicResponse(json.dumps([
            {"name": "Test", "email": "test@example.com", "amount": "100", "currency": "USD", "note": "test"},
        ]))

        with patch("app.services.ai_parser.anthropic.Anthropic") as mock_client_class:
            mock_client = MagicMock()
            mock_client.messages.create.return_value = mock_response
            mock_client_class.return_value = mock_client

            result = parse_payouts("test input")
            assert isinstance(result, ParsedPayouts)

    def test_review_payouts_function(self):
        mock_response = MockAnthropicResponse(json.dumps({
            "items": [{"email": "test@example.com", "flags": [], "explanation": "OK"}],
            "audit_summary": "Test"
        }))

        with patch("app.services.ai_review.anthropic.Anthropic") as mock_client_class:
            mock_client = MagicMock()
            mock_client.messages.create.return_value = mock_response
            mock_client_class.return_value = mock_client

            payees = [ParsedPayee(name="Test", email="test@example.com", amount=Decimal("100"), currency="USD")]
            policy_results = [PolicyResult(decision=PolicyDecision.AUTO_APPROVED, reasons=[])]

            result = review_payouts(payees, policy_results)
            assert isinstance(result, AIReviewResponse)
