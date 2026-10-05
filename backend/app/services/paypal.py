import base64
import hashlib
import logging
import time
from dataclasses import dataclass
from decimal import Decimal

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class PayPalToken:
    access_token: str
    expires_at: float
    token_type: str = "Bearer"

    def is_expired(self, buffer_seconds: int = 60) -> bool:
        return time.time() >= (self.expires_at - buffer_seconds)


@dataclass
class PayoutItem:
    amount: Decimal
    currency: str
    receiver: str
    note: str
    sender_item_id: str
    recipient_type: str = "EMAIL"


@dataclass
class PayoutBatchResponse:
    batch_header: dict
    items: list[dict]


class PayPalClient:
    """PayPal Payouts API client with OAuth2 token management."""

    def __init__(self):
        self.client_id = settings.paypal_client_id
        self.client_secret = settings.paypal_client_secret
        self.base_url = settings.paypal_base_url
        self._token: PayPalToken | None = None
        self._client = httpx.AsyncClient(timeout=30.0)

    async def _get_token(self) -> PayPalToken:
        """Get valid OAuth2 token, refreshing if expired."""
        if self._token and not self._token.is_expired():
            return self._token

        auth = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        headers = {
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = {"grant_type": "client_credentials"}

        response = await self._client.post(
            f"{self.base_url}/v1/oauth2/token",
            headers=headers,
            data=data,
        )
        response.raise_for_status()
        token_data = response.json()

        self._token = PayPalToken(
            access_token=token_data["access_token"],
            expires_at=time.time() + token_data["expires_in"],
            token_type=token_data.get("token_type", "Bearer"),
        )
        logger.info("Obtained new PayPal access token")
        return self._token

    async def _authenticated_request(
        self,
        method: str,
        path: str,
        json_data: dict | None = None,
        headers: dict | None = None,
    ) -> httpx.Response:
        """Make authenticated request to PayPal API."""
        token = await self._get_token()
        request_headers = {
            "Authorization": f"{token.token_type} {token.access_token}",
            "Content-Type": "application/json",
            "PayPal-Request-Id": f"req_{int(time.time() * 1000)}",
        }
        if headers:
            request_headers.update(headers)

        url = f"{self.base_url}{path}"
        response = await self._client.request(method, url, headers=request_headers, json=json_data)
        return response  # type: ignore[no-any-return]

    async def create_payout_batch(
        self,
        sender_batch_id: str,
        items: list[PayoutItem],
        email_subject: str = "You have a payout!",
        email_message: str = "You have received a payment.",
    ) -> PayoutBatchResponse:
        """
        Create a payout batch.

        Args:
            sender_batch_id: Unique ID for idempotency
            items: List of PayoutItem objects
            email_subject: Subject for recipient notification email
            email_message: Message for recipient notification email

        Returns:
            PayoutBatchResponse with batch_header and items
        """
        payout_items = []
        for item in items:
            payout_items.append({
                "recipient_type": item.recipient_type,
                "amount": {"value": f"{item.amount:.2f}", "currency": item.currency},
                "receiver": item.receiver,
                "note": item.note,
                "sender_item_id": item.sender_item_id,
            })

        payload = {
            "sender_batch_header": {
                "sender_batch_id": sender_batch_id,
                "email_subject": email_subject,
                "email_message": email_message,
            },
            "items": payout_items,
        }

        response = await self._authenticated_request(
            "POST",
            "/v1/payments/payouts",
            json_data=payload,
        )

        if response.status_code == 401 and self._token:
            # Token might be stale, clear and retry once
            self._token = None
            response = await self._authenticated_request(
                "POST",
                "/v1/payments/payouts",
                json_data=payload,
            )

        response.raise_for_status()
        data = response.json()
        logger.info(f"Created payout batch {sender_batch_id}, PayPal batch ID: {data.get('batch_header', {}).get('payout_batch_id')}")
        return PayoutBatchResponse(
            batch_header=data.get("batch_header", {}),
            items=data.get("items", []),
        )

    async def get_payout_batch(self, payout_batch_id: str) -> dict:
        """Get payout batch details."""
        response = await self._authenticated_request(
            "GET",
            f"/v1/payments/payouts/{payout_batch_id}",
        )
        response.raise_for_status()
        return response.json()  # type: ignore[no-any-return]

    async def get_payout_item(self, payout_item_id: str) -> dict:
        """Get individual payout item details."""
        response = await self._authenticated_request(
            "GET",
            f"/v1/payments/payouts-item/{payout_item_id}",
        )
        response.raise_for_status()
        return response.json()  # type: ignore[no-any-return]

    async def verify_webhook_signature(
        self,
        transmission_id: str,
        timestamp: str,
        webhook_id: str,
        event_body: str,
        cert_url: str,
        actual_signature: str,
    ) -> bool:
        """
        Verify PayPal webhook signature.

        Args:
            transmission_id: PayPal-Transmission-Id header
            timestamp: PayPal-Transmission-Time header
            webhook_id: Configured webhook ID
            event_body: Raw request body
            cert_url: PayPal-Cert-Url header
            actual_signature: PayPal-Transmission-Sig header

        Returns:
            True if signature is valid
        """
        payload = f"{transmission_id}|{timestamp}|{webhook_id}|{hashlib.sha256(event_body.encode()).hexdigest()}"

        # Fetch certificate
        cert_response = await self._client.get(cert_url)
        cert_response.raise_for_status()
        cert_pem = cert_response.text

        # Extract public key (simplified - in production use proper cert parsing)
        # PayPal uses RSA-SHA256 with PKCS#1 v1.5 padding
        from cryptography.hazmat.backends import default_backend
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding

        public_key = serialization.load_pem_public_key(cert_pem.encode(), backend=default_backend())

        try:
            public_key.verify(
                base64.b64decode(actual_signature),
                payload.encode(),
                padding.PKCS1v15(),
                hashes.SHA256(),
            )
            return True
        except Exception as e:
            logger.warning(f"Webhook signature verification failed: {e}")
            return False

    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()


_paypal_client: PayPalClient | None = None


def get_paypal_client() -> PayPalClient:
    """Get singleton PayPal client."""
    global _paypal_client
    if _paypal_client is None:
        _paypal_client = PayPalClient()
    return _paypal_client

