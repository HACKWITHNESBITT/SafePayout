import { formatAmount } from "../utils/format";
import type { PayoutItemResponse, PolicyDecision, HumanDecision } from "../types/api";
import styles from "./PolicyBadge.module.css";

interface PolicyBadgeProps {
  decision: PolicyDecision | null;
  size?: "sm" | "md" | "lg";
}

const decisionConfig: Record<PolicyDecision, { label: string; icon: string; variant: string }> = {
  AUTO_APPROVED: { label: "Auto-approved", icon: "✓", variant: "approved" },
  NEEDS_REVIEW: { label: "Needs review", icon: "⚠", variant: "review" },
  BLOCKED: { label: "Blocked", icon: "✕", variant: "blocked" },
};

export function PolicyBadge({ decision, size = "md" }: PolicyBadgeProps) {
  if (!decision) {
    return <span className={`${styles.badge} ${styles[`size-${size}`]} ${styles.unknown}`}>Unknown</span>;
  }

  const config = decisionConfig[decision];
  
  if (!config) {
    return <span className={`${styles.badge} ${styles[`size-${size}`]} ${styles.unknown}`}>Unknown config for {decision}</span>;
  }
  
  return (
    <span
      className={`${styles.badge} ${styles[`size-${size}`]} ${styles[config.variant]}`}
      aria-label={config.label}
    >
      <span className={styles.icon} aria-hidden="true">{config.icon}</span>
      <span className={styles.label}>{config.label}</span>
    </span>
  );
}

interface HumanDecisionBadgeProps {
  decision: HumanDecision;
  size?: "sm" | "md" | "lg";
}

const humanDecisionConfig: Record<HumanDecision, { label: string; variant: string }> = {
  PENDING: { label: "Pending", variant: "pending" },
  APPROVED: { label: "Approved", variant: "approved" },
  REJECTED: { label: "Rejected", variant: "rejected" },
};

export function HumanDecisionBadge({ decision, size = "md" }: HumanDecisionBadgeProps) {
  const config = humanDecisionConfig[decision];
  return (
    <span className={`${styles.badge} ${styles[`size-${size}`]} ${styles[config.variant]}`}>
      {config.label}
    </span>
  );
}

interface PayPalStatusBadgeProps {
  status: PayoutItemResponse["paypal_item_status"];
  size?: "sm" | "md" | "lg";
}

const paypalStatusConfig: Record<PayoutItemResponse["paypal_item_status"], { label: string; variant: string }> = {
  PENDING: { label: "Queued", variant: "pending" },
  SUCCESS: { label: "Sent", variant: "success" },
  FAILED: { label: "Failed", variant: "failed" },
  UNCLAIMED: { label: "Unclaimed", variant: "unclaimed" },
  BLOCKED: { label: "Blocked", variant: "blocked" },
  REFUNDED: { label: "Refunded", variant: "refunded" },
  REVERSED: { label: "Reversed", variant: "reversed" },
};

export function PayPalStatusBadge({ status, size = "md" }: PayPalStatusBadgeProps) {
  const config = paypalStatusConfig[status] || { label: status, variant: "unknown" };
  return (
    <span className={`${styles.badge} ${styles[`size-${size}`]} ${styles[config.variant]}`}>
      {config.label}
    </span>
  );
}

interface AmountCellProps {
  amount: string;
  currency?: string;
}

export function AmountCell({ amount, currency = "USD" }: AmountCellProps) {
  return (
    <span className={styles.amount} data-currency={currency}>
      {formatAmount(amount, currency)}
    </span>
  );
}

interface RunStatusBadgeProps {
  status: PayoutItemResponse["paypal_item_status"] | "DRAFT" | "REVIEW" | "APPROVED" | "EXECUTING" | "COMPLETED" | "PARTIAL" | "FAILED";
}

const runStatusConfig: Record<string, { label: string; variant: string }> = {
  DRAFT: { label: "Draft", variant: "draft" },
  REVIEW: { label: "In Review", variant: "review" },
  APPROVED: { label: "Approved", variant: "approved" },
  EXECUTING: { label: "Executing", variant: "executing" },
  COMPLETED: { label: "Completed", variant: "completed" },
  PARTIAL: { label: "Partial", variant: "partial" },
  FAILED: { label: "Failed", variant: "failed" },
};

export function RunStatusBadge({ status }: RunStatusBadgeProps) {
  const config = runStatusConfig[status] || { label: status, variant: "unknown" };
  return (
    <span className={`${styles.runBadge} ${styles[config.variant]}`}>
      {config.label}
    </span>
  );
}