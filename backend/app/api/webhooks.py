import json
import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import AuditEvent, PayoutItem, PayoutRun, PayPalItemStatus, RunStatus
from app.services.paypal import get_paypal_client

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])


async def verify_paypal_webhook(
    request: Request,
    paypal_transmission_id: str = Header(..., alias="PayPal-Transmission-Id"),
    paypal_transmission_time: str = Header(..., alias="PayPal-Transmission-Time"),
    paypal_cert_url: str = Header(..., alias="PayPal-Cert-Url"),
    paypal_transmission_sig: str = Header(..., alias="PayPal-Transmission-Sig"),
    paypal_auth_algo: str = Header(..., alias="PayPal-Auth-Algo"),
) -> dict:
    """Verify PayPal webhook signature and return parsed event body."""
    settings = get_paypal_client()
    webhook_id = settings.client_id  # Note: should be PAYPAL_WEBHOOK_ID from env

    body = await request.body()
    event_body = body.decode()

    # Verify signature
    is_valid = await settings.verify_webhook_signature(
        transmission_id=paypal_transmission_id,
        timestamp=paypal_transmission_time,
        webhook_id=webhook_id,
        event_body=event_body,
        cert_url=paypal_cert_url,
        actual_signature=paypal_transmission_sig,
    )

    if not is_valid:
        logger.warning("Invalid PayPal webhook signature")
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    return json.loads(event_body)  # type: ignore[no-any-return]


@router.post("/paypal")
async def paypal_webhook(
    request: Request,
    paypal_transmission_id: str = Header(..., alias="PayPal-Transmission-Id"),
    paypal_transmission_time: str = Header(..., alias="PayPal-Transmission-Time"),
    paypal_cert_url: str = Header(..., alias="PayPal-Cert-Url"),
    paypal_transmission_sig: str = Header(..., alias="PayPal-Transmission-Sig"),
    paypal_auth_algo: str = Header(..., alias="PayPal-Auth-Algo"),
    db: Session = Depends(get_db),
):
    """
    Handle PayPal webhook events for payouts.

    Supported events:
    - PAYMENT.PAYOUTSBATCH.SUCCESS
    - PAYMENT.PAYOUTSBATCH.DENIED
    - PAYMENT.PAYOUTSBATCH.PENDING
    - PAYMENT.PAYOUTS-ITEM.SUCCESS
    - PAYMENT.PAYOUTS-ITEM.FAILED
    - PAYMENT.PAYOUTS-ITEM.UNCLAIMED
    - PAYMENT.PAYOUTS-ITEM.BLOCKED
    - PAYMENT.PAYOUTS-ITEM.REFUNDED
    - PAYMENT.PAYOUTS-ITEM.REVERSED
    """
    if db is None:
        db = next(get_db())

    try:
        event = await verify_paypal_webhook(
            request,
            paypal_transmission_id,
            paypal_transmission_time,
            paypal_cert_url,
            paypal_transmission_sig,
            paypal_auth_algo,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Webhook verification error: {e}")
        raise HTTPException(status_code=400, detail="Webhook verification failed") from e

    event_type = event.get("event_type", "")
    resource = event.get("resource", {})

    logger.info(f"Received PayPal webhook: {event_type}")

    try:
        if event_type.startswith("PAYMENT.PAYOUTSBATCH"):
            await handle_batch_event(db, event_type, resource, event)
        elif event_type.startswith("PAYMENT.PAYOUTS-ITEM"):
            await handle_item_event(db, event_type, resource, event)
        else:
            logger.info(f"Unhandled event type: {event_type}")

        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Error processing webhook: {e}")
        raise HTTPException(status_code=500, detail="Webhook processing failed") from e

    return {"status": "ok"}


async def handle_batch_event(
    db: Session,
    event_type: str,
    resource: dict,
    full_event: dict,
):
    """Handle batch-level webhook events."""
    payout_batch_id = resource.get("batch_header", {}).get("payout_batch_id")
    sender_batch_id = resource.get("batch_header", {}).get("sender_batch_id")

    if not payout_batch_id or not sender_batch_id:
        logger.warning("Missing batch IDs in webhook")
        return

    run = db.query(PayoutRun).filter(PayoutRun.sender_batch_id == sender_batch_id).first()
    if not run:
        logger.warning(f"Run not found for sender_batch_id: {sender_batch_id}")
        return

    run.paypal_batch_id = payout_batch_id

    if event_type == "PAYMENT.PAYOUTSBATCH.SUCCESS":
        run.status = RunStatus.COMPLETED
    elif event_type == "PAYMENT.PAYOUTSBATCH.DENIED":
        run.status = RunStatus.FAILED
    elif event_type == "PAYMENT.PAYOUTSBATCH.PENDING":
        run.status = RunStatus.EXECUTING

    db.add(AuditEvent(
        run_id=run.id,
        type=f"webhook.batch.{event_type.lower().replace('.', '_')}",
        detail={
            "payout_batch_id": payout_batch_id,
            "sender_batch_id": sender_batch_id,
            "resource": resource,
        },
    ))


async def handle_item_event(
    db: Session,
    event_type: str,
    resource: dict,
    full_event: dict,
):
    """Handle item-level webhook events."""
    payout_item_id = resource.get("payout_item_id")
    payout_batch_id = resource.get("payout_batch_id")
    sender_item_id = resource.get("sender_item_id")
    status = resource.get("status", "")
    amount = resource.get("amount", {})
    receiver = resource.get("receiver", "")

    if not payout_item_id:
        logger.warning("Missing payout_item_id in webhook")
        return

    # Find item by paypal_item_id or sender_item_id
    item = None
    if sender_item_id:
        item = db.query(PayoutItem).filter(PayoutItem.paypal_item_id == sender_item_id).first()
    if not item:
        item = db.query(PayoutItem).filter(PayoutItem.paypal_item_id == payout_item_id).first()

    if not item:
        logger.warning(f"Item not found for payout_item_id: {payout_item_id}, sender_item_id: {sender_item_id}")
        return

    # Update item status
    status_map = {
        "SUCCESS": PayPalItemStatus.SUCCESS,
        "FAILED": PayPalItemStatus.FAILED,
        "UNCLAIMED": PayPalItemStatus.UNCLAIMED,
        "BLOCKED": PayPalItemStatus.BLOCKED,
        "REFUNDED": PayPalItemStatus.REFUNDED,
        "REVERSED": PayPalItemStatus.REVERSED,
        "PENDING": PayPalItemStatus.PENDING,
    }

    new_status = status_map.get(status, PayPalItemStatus.PENDING)
    item.paypal_item_status = new_status
    item.paypal_item_id = payout_item_id

    db.add(AuditEvent(
        run_id=item.run_id,
        type=f"webhook.item.{event_type.lower().replace('.', '_')}",
        detail={
            "payout_item_id": payout_item_id,
            "payout_batch_id": payout_batch_id,
            "sender_item_id": sender_item_id,
            "status": status,
            "amount": amount,
            "receiver": receiver,
            "resource": resource,
        },
    ))

    # Check if all items in run are done
    run = db.query(PayoutRun).filter(PayoutRun.id == item.run_id).first()
    if run:
        pending_items = db.query(PayoutItem).filter(
            PayoutItem.run_id == run.id,
            PayoutItem.paypal_item_status.in_([PayPalItemStatus.PENDING]),
        ).count()

        if pending_items == 0:
            # All items processed
            failed_items = db.query(PayoutItem).filter(
                PayoutItem.run_id == run.id,
                PayoutItem.paypal_item_status == PayPalItemStatus.FAILED,
            ).count()
            unclaimed_items = db.query(PayoutItem).filter(
                PayoutItem.run_id == run.id,
                PayoutItem.paypal_item_status == PayPalItemStatus.UNCLAIMED,
            ).count()

            if failed_items == 0 and unclaimed_items == 0:
                run.status = RunStatus.COMPLETED
            elif failed_items > 0 and unclaimed_items == 0 and failed_items == len(run.items):
                run.status = RunStatus.FAILED
            else:
                run.status = RunStatus.PARTIAL

