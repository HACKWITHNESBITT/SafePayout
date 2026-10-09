#import csv
#import io
#from uuid import uuid4
#
#from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
#from sqlalchemy.orm import Session
#
#from app.db import get_db
#from app.models import (
#    AuditEvent,
#    HumanDecision,
#    PayoutItem,
#    PayoutRun,
#    PolicyDecision,
#    RunStatus,
#)
#from app.schemas import (
#    AuditSummary,
#    PayoutItemDecision,
#    PayoutItemResponse,
#    PayoutRunCreate,
#    PayoutRunResponse,
#)
#from app.services.ai_parser import parse_payouts
#from app.services.ai_review import review_payouts
#from app.services.paypal import PayoutItem as PayPalPayoutItem
#from app.services.paypal import get_paypal_client
#from app.services.policy import PolicyConfig, evaluate_batch
#
#router = APIRouter()
#
#
#def _parse_csv(content: str) -> list[dict]:
#    """Parse CSV content into list of dicts."""
#    reader = csv.DictReader(io.StringIO(content))
#    return list(reader)
#
#
#@router.post("", response_model=PayoutRunResponse, status_code=status.HTTP_201_CREATED)
#def create_run(payload: PayoutRunCreate, db: Session = Depends(get_db)):
#    run = PayoutRun(
#        budget_cap=payload.budget_cap,
#        sender_batch_id=f"sp_{uuid4().hex[:24]}",
#        status=RunStatus.DRAFT,
#    )
#    db.add(run)
#    db.commit()
#    db.refresh(run)
#    return run
#
#
#@router.post("/{run_id}/upload", response_model=PayoutRunResponse)
#async def upload_file(
#    run_id: int,
#    file: UploadFile = File(...),
#    db: Session = Depends(get_db),
#):
#    run = db.query(PayoutRun).filter(PayoutRun.id == run_id).first()
#    if not run:
#        raise HTTPException(status_code=404, detail="Run not found")
#    if run.status != RunStatus.DRAFT:
#        raise HTTPException(status_code=400, detail="Run is not in DRAFT status")
#
#    content = (await file.read()).decode()
#    is_csv = (file.filename or "").endswith(".csv")
#
#    # Parse with AI
#    parsed = parse_payouts(content, is_csv=is_csv)
#
#    # Create items
#    items = []
#    for p in parsed.payees:
#        item = PayoutItem(
#            run_id=run.id,
#            name=p.name,
#            email=p.email,
#            amount=p.amount,
#            currency=p.currency,
#            note=p.note,
#        )
#        db.add(item)
#        items.append(item)
#
#    db.commit()
#
#    # Run policy engine
#    policy_items = [
#        {"name": p.name, "email": p.email, "amount": str(p.amount), "currency": p.currency, "note": p.note}
#        for p in parsed.payees
#    ]
#    config = PolicyConfig.default()
#    policy_results = evaluate_batch(policy_items, config, budget_cap=run.budget_cap)
#
#    # Update items with policy results
#    for item, result in zip(items, policy_results, strict=True):
#        item.policy_decision = result.decision  # type: ignore[assignment]
#        item.policy_reasons = [{"code": r.code.value, "message": r.message, "severity": r.severity.value} for r in result.reasons]  # type: ignore[assignment]
#        if result.decision == PolicyDecision.AUTO_APPROVED:
#            item.human_decision = HumanDecision.APPROVED  # type: ignore[assignment]
#        elif result.decision == PolicyDecision.BLOCKED:
#            item.human_decision = HumanDecision.REJECTED  # type: ignore[assignment]
#        else:
#            item.human_decision = HumanDecision.PENDING  # type: ignore[assignment]
#
#    # Run AI review
#    review = review_payouts(parsed.payees, policy_results)
#    for item, review_item in zip(items, review.items, strict=True):
#        item.ai_flags = {"flags": [{"type": f.type, "message": f.message} for f in review_item.flags], "explanation": review_item.explanation}
#
#    run.status = RunStatus.REVIEW
#    db.add(AuditEvent(
#        run_id=run.id,
#        type="run.created",
#        detail={"item_count": len(items), "parsed_summary": parsed.raw_input_summary},
#    ))
#
#    db.commit()
#    db.refresh(run)
#    return run
#
#
#@router.post("/{run_id}/text", response_model=PayoutRunResponse)
#async def upload_text(
#    run_id: int,
#    text: str,
#    db: Session = Depends(get_db),
#):
#    """Upload free-text payout instructions."""
#    run = db.query(PayoutRun).filter(PayoutRun.id == run_id).first()
#    if not run:
#        raise HTTPException(status_code=404, detail="Run not found")
#    if run.status != RunStatus.DRAFT:
#        raise HTTPException(status_code=400, detail="Run is not in DRAFT status")
#
#    parsed = parse_payouts(text, is_csv=False)
#
#    items = []
#    for p in parsed.payees:
#        item = PayoutItem(
#            run_id=run.id,
#            name=p.name,
#            email=p.email,
#            amount=p.amount,
#            currency=p.currency,
#            note=p.note,
#        )
#        db.add(item)
#        items.append(item)
#
#    db.commit()
#
#    policy_items = [
#        {"name": p.name, "email": p.email, "amount": str(p.amount), "currency": p.currency, "note": p.note}
#        for p in parsed.payees
#    ]
#    config = PolicyConfig.default()
#    policy_results = evaluate_batch(policy_items, config, budget_cap=run.budget_cap)
#
#    for item, result in zip(items, policy_results, strict=True):
#        item.policy_decision = result.decision  # type: ignore[assignment]
#        item.policy_reasons = [{"code": r.code.value, "message": r.message, "severity": r.severity.value} for r in result.reasons]  # type: ignore[assignment]
#        if result.decision == PolicyDecision.AUTO_APPROVED:
#            item.human_decision = HumanDecision.APPROVED  # type: ignore[assignment]
#        elif result.decision == PolicyDecision.BLOCKED:
#            item.human_decision = HumanDecision.REJECTED  # type: ignore[assignment]
#        else:
#            item.human_decision = HumanDecision.PENDING  # type: ignore[assignment]
#
#    review = review_payouts(parsed.payees, policy_results)
#    for item, review_item in zip(items, review.items, strict=True):
#        item.ai_flags = {"flags": [{"type": f.type, "message": f.message} for f in review_item.flags], "explanation": review_item.explanation}  # type: ignore[assignment]
#
#    run.status = RunStatus.REVIEW
#    db.add(AuditEvent(
#        run_id=run.id,
#        type="run.created",
#        detail={"item_count": len(items), "parsed_summary": parsed.raw_input_summary},
#    ))
#
#    db.commit()
#    db.refresh(run)
#    return run
#
#
#@router.get("/{run_id}", response_model=PayoutRunResponse)
#def get_run(run_id: int, db: Session = Depends(get_db)):
#    run = db.query(PayoutRun).filter(PayoutRun.id == run_id).first()
#    if not run:
#        raise HTTPException(status_code=404, detail="Run not found")
#    return run
#
#
#@router.get("/{run_id}/items", response_model=list[PayoutItemResponse])
#def get_run_items(run_id: int, db: Session = Depends(get_db)):
#    run = db.query(PayoutRun).filter(PayoutRun.id == run_id).first()
#    if not run:
#        raise HTTPException(status_code=404, detail="Run not found")
#    return run.items
#
#
#@router.get("", response_model=list[PayoutRunResponse])
#def list_runs(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
#    runs = db.query(PayoutRun).offset(skip).limit(limit).all()
#    return runs
#
#
#@router.post("/{run_id}/items/{item_id}/decision", response_model=PayoutItemResponse)
#def set_item_decision(
#    run_id: int,
#    item_id: int,
#    decision: PayoutItemDecision,
#    db: Session = Depends(get_db),
#):
#    item = db.query(PayoutItem).filter(PayoutItem.id == item_id, PayoutItem.run_id == run_id).first()
#    if not item:
#        raise HTTPException(status_code=404, detail="Item not found")
#
#    if item.policy_decision == PolicyDecision.BLOCKED:
#        raise HTTPException(status_code=400, detail="Blocked items cannot be approved")
#
#    item.human_decision = decision.human_decision  # type: ignore[assignment]
#    db.add(AuditEvent(
#        run_id=run_id,
#        type=f"item.decision.{decision.human_decision.value.lower()}",
#        detail={"item_id": item_id, "email": item.email, "amount": str(item.amount)},
#    ))
#    db.commit()
#    db.refresh(item)
#    return item
#
#
#@router.post("/{run_id}/approve-all", response_model=PayoutRunResponse)
#def approve_all_pending(
#    run_id: int,
#    db: Session = Depends(get_db),
#):
#    """Approve all items that are NEEDS_REVIEW."""
#    run = db.query(PayoutRun).filter(PayoutRun.id == run_id).first()
#    if not run:
#        raise HTTPException(status_code=404, detail="Run not found")
#
#    pending_items = db.query(PayoutItem).filter(
#        PayoutItem.run_id == run_id,
#        PayoutItem.policy_decision == PolicyDecision.NEEDS_REVIEW,
#        PayoutItem.human_decision == HumanDecision.PENDING,
#    ).all()
#
#    for item in pending_items:
#        item.human_decision = HumanDecision.APPROVED
#
#    db.add(AuditEvent(
#        run_id=run_id,
#        type="run.approve_all_pending",
#        detail={"count": len(pending_items)},
#    ))
#    db.commit()
#    db.refresh(run)
#    return run
#
#
#@router.post("/{run_id}/execute", response_model=PayoutRunResponse)
#async def execute_run(
#    run_id: int,
#    db: Session = Depends(get_db),
#):
#    run = db.query(PayoutRun).filter(PayoutRun.id == run_id).first()
#    if not run:
#        raise HTTPException(status_code=404, detail="Run not found")
#
#    if run.status not in [RunStatus.REVIEW, RunStatus.APPROVED]:
#        raise HTTPException(status_code=400, detail=f"Run must be in REVIEW or APPROVED status, current: {run.status.value}")
#
#    # Check all non-blocked items have human decision
#    items = db.query(PayoutItem).filter(PayoutItem.run_id == run_id).all()
#    for item in items:
#        if item.policy_decision != PolicyDecision.BLOCKED and item.human_decision == HumanDecision.PENDING:
#            raise HTTPException(status_code=400, detail=f"Item {item.id} ({item.email}) needs human decision")
#
#    # Filter approved items
#    approved_items = [
#        item for item in items
#        if item.human_decision == HumanDecision.APPROVED
#        and item.policy_decision != PolicyDecision.BLOCKED
#    ]
#
#    if not approved_items:
#        raise HTTPException(status_code=400, detail="No approved items to execute")
#
#    run.status = RunStatus.EXECUTING
#    db.commit()
#
#    # Create PayPal payout batch
#    paypal_items = [
#        PayPalPayoutItem(
#            amount=item.amount,
#            currency=item.currency,
#            receiver=item.email,
#            note=item.note or "Payout from SafePayout",
#            sender_item_id=f"item_{item.id}",
#        )
#        for item in approved_items
#    ]
#
#    paypal_client = get_paypal_client()
#    try:
#        response = await paypal_client.create_payout_batch(
#            sender_batch_id=run.sender_batch_id,
#            items=paypal_items,
#        )
#    except Exception as e:
#        run.status = RunStatus.FAILED
#        db.add(AuditEvent(
#            run_id=run.id,
#            type="run.execute.failed",
#            detail={"error": str(e)},
#        ))
#        db.commit()
#        raise HTTPException(status_code=500, detail=f"PayPal payout failed: {e}") from e
#
#    run.paypal_batch_id = response.batch_header.get("payout_batch_id")
#    run.status = RunStatus.EXECUTING
#
#    # Update item paypal IDs
#    for item, pp_item in zip(approved_items, response.items, strict=True):
#        item.paypal_item_id = pp_item.get("payout_item_id")
#
#    db.add(AuditEvent(
#        run_id=run.id,
#        type="run.executed",
#        detail={
#            "payout_batch_id": run.paypal_batch_id,
#            "item_count": len(approved_items),
#        },
#    ))
#    db.commit()
#    db.refresh(run)
#    return run
#
#
#@router.get("/{run_id}/audit", response_model=AuditSummary)
#def get_audit_summary(run_id: int, db: Session = Depends(get_db)):
#    run = db.query(PayoutRun).filter(PayoutRun.id == run_id).first()
#    if not run:
#        raise HTTPException(status_code=404, detail="Run not found")
#
#    items = run.items
#    total_amount = sum(item.amount for item in items)
#    auto_approved = sum(1 for i in items if i.policy_decision == PolicyDecision.AUTO_APPROVED)
#    needs_review = sum(1 for i in items if i.policy_decision == PolicyDecision.NEEDS_REVIEW)
#    blocked = sum(1 for i in items if i.policy_decision == PolicyDecision.BLOCKED)
#    human_approved = sum(1 for i in items if i.human_decision == HumanDecision.APPROVED)
#    human_rejected = sum(1 for i in items if i.human_decision == HumanDecision.REJECTED)
#
#    events = db.query(AuditEvent).filter(AuditEvent.run_id == run_id).order_by(AuditEvent.created_at).all()
#
#    return AuditSummary(
#        run_id=run.id,
#        run_status=run.status,  # type: ignore[arg-type]
#        total_items=len(items),
#        auto_approved=auto_approved,
#        needs_review=needs_review,
#        blocked=blocked,
#        human_approved=human_approved,
#        human_rejected=human_rejected,
#        total_amount=total_amount,  # type: ignore[arg-type]
#        budget_cap=run.budget_cap,
#        paypal_batch_id=run.paypal_batch_id,
#        items=items,  # type: ignore[arg-type]
#        events=events,  # type: ignore[arg-type]
#    )
#
