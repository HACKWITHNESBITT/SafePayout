#import json
#import logging
#from decimal import Decimal
#
#import anthropic
#
#from app.config import get_settings
#from app.schemas import AIReviewResponse, ParsedPayee, PolicyDecision
#from app.services.policy import PolicyReason, PolicyReasonCode, PolicyResult
#
#logger = logging.getLogger(__name__)
#settings = get_settings()
#
#
#class AIReviewer:
#    def __init__(self, client: anthropic.Anthropic | None = None):
#        self.client = client or anthropic.Anthropic(api_key=settings.anthropic_api_key)
#        self.model = settings.anthropic_model
#        self._system_prompt = self._load_system_prompt()
#
#    def _load_system_prompt(self) -> str:
#        try:
#            with open("backend/app/prompts/reviewer_system.md") as f:
#                return f.read()
#        except FileNotFoundError:
#            logger.warning("Reviewer system prompt not found, using default")
#            return "Review payees against policy results. Return JSON with flags and audit summary."
#
#    def review(
#        self,
#        parsed_payees: list[ParsedPayee],
#        policy_results: list[PolicyResult],
#        payee_histories: dict[str, dict] | None = None,
#        budget_cap: Decimal | None = None,
#    ) -> AIReviewResponse:
#        """
#        Generate human-readable flags and explanations for each item,
#        plus an audit summary of the run.
#        """
#        items_context = self._build_items_context(parsed_payees, policy_results, payee_histories)
#        user_prompt = self._build_user_prompt(items_context, budget_cap)
#
#        try:
#            response = self.client.messages.create(  # type: ignore[call-overload]
#                model=self.model,
#                max_tokens=4096,
#                system=self._system_prompt,
#                messages=[{"role": "user", "content": user_prompt}],
#            )
#            content = response.content[0].text
#            return self._parse_and_validate(content)
#        except Exception as e:
#            logger.warning(f"LLM review failed, falling back to deterministic review: {e}")
#            fallback = self._deterministic_review(parsed_payees, policy_results, payee_histories, budget_cap)
#            return AIReviewResponse.model_validate(fallback)
#
#    def _build_items_context(
#        self,
#        parsed_payees: list[ParsedPayee],
#        policy_results: list[PolicyResult],
#        payee_histories: dict[str, dict] | None = None,
#    ) -> list[dict]:
#        payee_histories = payee_histories or {}
#        context = []
#
#        for payee, result in zip(parsed_payees, policy_results, strict=True):
#            history = payee_histories.get(payee.email.lower(), {})
#            avg_amount = history.get("avg_amount")
#            reasons = [
#                {
#                    "code": r.code.value if hasattr(r.code, "value") else str(r.code),
#                    "message": r.message,
#                    "severity": r.severity.value if hasattr(r.severity, "value") else str(r.severity),
#                    "details": r.details,
#                }
#                for r in result.reasons
#            ]
#
#            context.append({
#                "email": payee.email,
#                "name": payee.name,
#                "amount": str(payee.amount),
#                "currency": payee.currency,
#                "note": payee.note,
#                "policy_decision": result.decision.value if hasattr(result.decision, "value") else str(result.decision),
#                "policy_reasons": reasons,
#                "history": {
#                    "avg_amount": str(avg_amount) if avg_amount else None,
#                    "total_payments": history.get("total_payments", 0),
#                },
#            })
#
#        return context
#
#    def _build_user_prompt(self, items_context: list[dict], budget_cap: Decimal | None) -> str:
#        total_amount = sum(Decimal(item["amount"]) for item in items_context)
#        summary = {
#            "total_items": len(items_context),
#            "total_amount": str(total_amount),
#            "budget_cap": str(budget_cap) if budget_cap else None,
#            "decisions": {
#                "auto_approved": sum(1 for i in items_context if i["policy_decision"] == "AUTO_APPROVED"),
#                "needs_review": sum(1 for i in items_context if i["policy_decision"] == "NEEDS_REVIEW"),
#                "blocked": sum(1 for i in items_context if i["policy_decision"] == "BLOCKED"),
#            },
#            "items": items_context,
#        }
#        return f"Review these payout items and produce flags + audit summary:\n```json\n{json.dumps(summary, indent=2)}\n```"
#
#    def _parse_and_validate(self, content: str) -> AIReviewResponse:
#        data = json.loads(content)
#        return AIReviewResponse.model_validate(data)
#
#    def _deterministic_review(
#        self,
#        parsed_payees: list[ParsedPayee],
#        policy_results: list[PolicyResult],
#        payee_histories: dict[str, dict] | None = None,
#        budget_cap: Decimal | None = None,
#    ) -> dict:
#        """Fallback deterministic review when LLM fails."""
#        items = []
#        payee_histories = payee_histories or {}
#
#        for payee, result in zip(parsed_payees, policy_results, strict=True):
#            history = payee_histories.get(payee.email.lower(), {})
#            avg_amount = history.get("avg_amount")
#            flags = []
#            explanations = []
#
#            for reason in result.reasons:
#                flag = self._reason_to_flag(reason, payee, avg_amount)
#                if flag:
#                    flags.append(flag)
#                explanations.append(reason.message)
#
#            items.append({
#                "email": payee.email,
#                "flags": flags,
#                "explanation": "; ".join(explanations) if explanations else "No issues detected",
#            })
#
#        total_amount = sum(p.amount for p in parsed_payees)
#        auto = sum(1 for r in policy_results if r.decision == PolicyDecision.AUTO_APPROVED)
#        review = sum(1 for r in policy_results if r.decision == PolicyDecision.NEEDS_REVIEW)
#        blocked = sum(1 for r in policy_results if r.decision == PolicyDecision.BLOCKED)
#
#        audit_parts = [
#            f"Run contains {len(parsed_payees)} payments totaling ${total_amount:.2f}.",
#            f"{auto} auto-approved, {review} need review, {blocked} blocked.",
#        ]
#        if budget_cap:
#            audit_parts.append(f"Budget cap: ${budget_cap:.2f}.")
#
#        return {
#            "items": items,
#            "audit_summary": " ".join(audit_parts),
#        }
#
#    def _reason_to_flag(
#        self,
#        reason: PolicyReason,
#        payee: ParsedPayee,
#        avg_amount: Decimal | None = None,
#    ) -> dict | None:
#        code = reason.code
#
#        flag_map = {
#            PolicyReasonCode.DUPLICATE_PAYEE_IN_RUN: ("duplicate", f"Duplicate payee in this run: {payee.email}"),
#            PolicyReasonCode.DUPLICATE_PAYMENT_RECENT: ("recent_duplicate", f"Similar payment to {payee.email} within recent period"),
#            PolicyReasonCode.INVALID_EMAIL_FORMAT: ("invalid_email", f"Invalid email format: {payee.email}"),
#            PolicyReasonCode.PAYEE_NOT_ALLOWLISTED: ("not_allowlisted", f"Payee {payee.email} not in allowlist"),
#            PolicyReasonCode.AMOUNT_EXCEEDS_PAYEE_CAP: ("over_payee_cap", f"Amount ${payee.amount:.2f} exceeds per-payee cap"),
#            PolicyReasonCode.TOTAL_EXCEEDS_BUDGET: ("over_budget", "Total would exceed budget cap"),
#            PolicyReasonCode.AMOUNT_ANOMALY: ("anomaly", f"Amount ${payee.amount:.2f} is unusual vs average ${avg_amount:.2f}") if avg_amount else ("anomaly", f"Amount ${payee.amount:.2f} is unusual"),
#        }
#
#        if code in flag_map:
#            flag_type, message = flag_map[code]
#            return {"type": flag_type, "message": message}
#        return None
#
#
#def review_payouts(
#    parsed_payees: list[ParsedPayee],
#    policy_results: list[PolicyResult],
#    payee_histories: dict[str, dict] | None = None,
#    budget_cap: Decimal | None = None,
#) -> AIReviewResponse:
#    """Convenience function for single-use review."""
#    reviewer = AIReviewer()
#    return reviewer.review(parsed_payees, policy_results, payee_histories, budget_cap)
