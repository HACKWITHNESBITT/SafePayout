from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import respx
from app.models import (
    HumanDecision,
    PayoutItem,
    PayoutRun,
    PolicyDecision,
    RunStatus,
)
from app.services.paypal import PayoutItem as PayPalPayoutItem
from app.services.paypal import PayPalClient, PayPalToken


class TestPayPalClient:
    @pytest.fixture
    def client(self):
        return PayPalClient()

    @pytest.mark.asyncio
    async def test_get_token_success(self, client):
        with respx.mock:
            respx.post("https://api-m.sandbox.paypal.com/v1/oauth2/token").mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "access_token": "test_token_123",
                        "token_type": "Bearer",
                        "expires_in": 3600,
                    },
                )
            )

            token = await client._get_token()
            assert token.access_token == "test_token_123"
            assert token.token_type == "Bearer"
            assert not token.is_expired()

    @pytest.mark.asyncio
    async def test_token_caching(self, client):
        with respx.mock:
            route = respx.post("https://api-m.sandbox.paypal.com/v1/oauth2/token").mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "access_token": "cached_token",
                        "token_type": "Bearer",
                        "expires_in": 3600,
                    },
                )
            )

            token1 = await client._get_token()
            token2 = await client._get_token()

            assert token1.access_token == "cached_token"
            assert token2.access_token == "cached_token"
            assert route.call_count == 1

    @pytest.mark.asyncio
    async def test_create_payout_batch_success(self, client):
        with respx.mock:
            respx.post("https://api-m.sandbox.paypal.com/v1/oauth2/token").mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "access_token": "test_token",
                        "token_type": "Bearer",
                        "expires_in": 3600,
                    },
                )
            )

            respx.post("https://api-m.sandbox.paypal.com/v1/payments/payouts").mock(
                return_value=httpx.Response(
                    201,
                    json={
                        "batch_header": {
                            "payout_batch_id": "batch_123",
                            "sender_batch_id": "sp_abc123",
                            "batch_status": "PENDING",
                        },
                        "items": [
                            {"payout_item_id": "item_1", "transaction_status": "SUCCESS"},
                            {"payout_item_id": "item_2", "transaction_status": "SUCCESS"},
                        ],
                    },
                )
            )

            items = [
                PayPalPayoutItem(amount=Decimal("100"), currency="USD", receiver="user1@example.com", note="Test 1", sender_item_id="item_1"),
                PayPalPayoutItem(amount=Decimal("200"), currency="USD", receiver="user2@example.com", note="Test 2", sender_item_id="item_2"),
            ]

            response = await client.create_payout_batch("sp_abc123", items)
            assert response.batch_header["payout_batch_id"] == "batch_123"
            assert len(response.items) == 2

    @pytest.mark.asyncio
    async def test_create_payout_batch_retry_on_401(self, client):
        with respx.mock:
            respx.post("https://api-m.sandbox.paypal.com/v1/oauth2/token").mock(
                return_value=httpx.Response(
                    200,
                    json={"access_token": "old_token", "token_type": "Bearer", "expires_in": 3600},
                )
            )

            payout_route = respx.post("https://api-m.sandbox.paypal.com/v1/payments/payouts").mock(
                side_effect=[
                    httpx.Response(401, json={"error": "Unauthorized"}),
                    httpx.Response(
                        201,
                        json={"batch_header": {"payout_batch_id": "batch_123"}, "items": []},
                    ),
                ]
            )

            respx.post("https://api-m.sandbox.paypal.com/v1/oauth2/token").mock(
                return_value=httpx.Response(
                    200,
                    json={"access_token": "new_token", "token_type": "Bearer", "expires_in": 3600},
                )
            )

            items = [PayPalPayoutItem(amount=Decimal("100"), currency="USD", receiver="user@example.com", note="Test", sender_item_id="item_1")]

            response = await client.create_payout_batch("sp_abc123", items)
            assert response.batch_header["payout_batch_id"] == "batch_123"
            assert payout_route.call_count == 2

    @pytest.mark.asyncio
    async def test_get_payout_batch(self, client):
        with respx.mock:
            respx.post("https://api-m.sandbox.paypal.com/v1/oauth2/token").mock(
                return_value=httpx.Response(200, json={"access_token": "test_token", "token_type": "Bearer", "expires_in": 3600})
            )

            respx.get("https://api-m.sandbox.paypal.com/v1/payments/payouts/batch_123").mock(
                return_value=httpx.Response(
                    200,
                    json={"batch_header": {"payout_batch_id": "batch_123", "batch_status": "SUCCESS"}, "items": []},
                )
            )

            result = await client.get_payout_batch("batch_123")
            assert result["batch_header"]["payout_batch_id"] == "batch_123"

    @pytest.mark.asyncio
    async def test_get_payout_item(self, client):
        with respx.mock:
            respx.post("https://api-m.sandbox.paypal.com/v1/oauth2/token").mock(
                return_value=httpx.Response(200, json={"access_token": "test_token", "token_type": "Bearer", "expires_in": 3600})
            )

            respx.get("https://api-m.sandbox.paypal.com/v1/payments/payouts-item/item_1").mock(
                return_value=httpx.Response(
                    200,
                    json={"payout_item_id": "item_1", "status": "SUCCESS", "amount": {"value": "100.00", "currency": "USD"}},
                )
            )

            result = await client.get_payout_item("item_1")
            assert result["payout_item_id"] == "item_1"


class TestPayPalToken:
    def test_is_expired_false(self):
        import time
        token = PayPalToken(access_token="test", expires_at=time.time() + 1000)
        assert not token.is_expired()

    def test_is_expired_true(self):
        import time
        token = PayPalToken(access_token="test", expires_at=time.time() - 100)
        assert token.is_expired()

    def test_is_expired_with_buffer(self):
        import time
        token = PayPalToken(access_token="test", expires_at=time.time() + 30)
        assert token.is_expired(buffer_seconds=60)


# Integration tests for runs API with PayPal

class TestRunsAPI:
    @pytest.mark.asyncio
    async def test_execute_run_success(self, client, db_session):
        from unittest.mock import AsyncMock

        run_resp = client.post("/runs", json={"budget_cap": "1000"})
        run_id = run_resp.json()["id"]

        run = db_session.query(PayoutRun).filter(PayoutRun.id == run_id).first()
        run.status = RunStatus.REVIEW
        db_session.commit()

        items = [
            PayoutItem(run_id=run_id, name="User 1", email="user1@example.com", amount=Decimal("100"), currency="USD", human_decision=HumanDecision.APPROVED, policy_decision=PolicyDecision.AUTO_APPROVED),
            PayoutItem(run_id=run_id, name="User 2", email="user2@example.com", amount=Decimal("200"), currency="USD", human_decision=HumanDecision.APPROVED, policy_decision=PolicyDecision.AUTO_APPROVED),
        ]
        for item in items:
            db_session.add(item)
        db_session.commit()

        with patch("app.api.runs.get_paypal_client") as mock:
            mock_client = AsyncMock()
            mock_client.create_payout_batch = AsyncMock(return_value=MagicMock(
                batch_header={"payout_batch_id": "batch_123"},
                items=[{"payout_item_id": "item_1"}, {"payout_item_id": "item_2"}],
            ))
            mock.return_value = mock_client

            execute_resp = client.post(f"/runs/{run_id}/execute")
            assert execute_resp.status_code == 200
            data = execute_resp.json()
            assert data["status"] == "EXECUTING"
            assert data["paypal_batch_id"] == "batch_123"

    @pytest.mark.asyncio
    async def test_execute_run_no_approved_items(self, client):
        run_resp = client.post("/runs", json={"budget_cap": "1000"})
        run_id = run_resp.json()["id"]

        execute_resp = client.post(f"/runs/{run_id}/execute")
        assert execute_resp.status_code == 400

    @pytest.mark.asyncio
    async def test_execute_run_pending_decisions(self, client, db_session):
        run_resp = client.post("/runs", json={"budget_cap": "1000"})
        run_id = run_resp.json()["id"]

        item = PayoutItem(run_id=run_id, name="User 1", email="user1@example.com", amount=Decimal("100"), currency="USD", human_decision=HumanDecision.PENDING, policy_decision=PolicyDecision.NEEDS_REVIEW)
        db_session.add(item)
        db_session.commit()

        execute_resp = client.post(f"/runs/{run_id}/execute")
        assert execute_resp.status_code == 400

    @pytest.mark.asyncio
    async def test_approve_all_pending(self, client, db_session):
        run_resp = client.post("/runs", json={"budget_cap": "1000"})
        run_id = run_resp.json()["id"]

        items = [
            PayoutItem(run_id=run_id, name="User 1", email="user1@example.com", amount=Decimal("100"), currency="USD", human_decision=HumanDecision.PENDING, policy_decision=PolicyDecision.NEEDS_REVIEW),
            PayoutItem(run_id=run_id, name="User 2", email="user2@example.com", amount=Decimal("200"), currency="USD", human_decision=HumanDecision.APPROVED, policy_decision=PolicyDecision.AUTO_APPROVED),
        ]
        for item in items:
            db_session.add(item)
        db_session.commit()

        resp = client.post(f"/runs/{run_id}/approve-all")
        assert resp.status_code == 200

        db_session.refresh(items[0])
        assert items[0].human_decision == HumanDecision.APPROVED


class TestWebhooks:
    @pytest.mark.asyncio
    async def test_paypal_webhook_batch_success(self, client, db_session):
        run = PayoutRun(sender_batch_id="sp_test123", budget_cap=Decimal("1000"), status=RunStatus.EXECUTING)
        db_session.add(run)
        db_session.commit()

        event = {
            "event_type": "PAYMENT.PAYOUTSBATCH.SUCCESS",
            "resource": {
                "batch_header": {
                    "payout_batch_id": "batch_123",
                    "sender_batch_id": "sp_test123",
                }
            },
        }

        with patch("app.api.webhooks.verify_paypal_webhook", new=AsyncMock(return_value=event)):
            resp = client.post(
                "/webhooks/paypal",
                json=event,
                headers={
                    "PayPal-Transmission-Id": "test_transmission",
                    "PayPal-Transmission-Time": "2024-01-01T00:00:00Z",
                    "PayPal-Cert-Url": "https://api-m.sandbox.paypal.com/v1/notifications/certs/CERT-123",
                    "PayPal-Transmission-Sig": "test_signature",
                    "PayPal-Auth-Algo": "SHA256withRSA",
                },
            )
        assert resp.status_code == 200

        db_session.refresh(run)
        assert run.status == RunStatus.COMPLETED
        assert run.paypal_batch_id == "batch_123"

