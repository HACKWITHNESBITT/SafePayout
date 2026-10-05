import { useState, useCallback, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, queryKeys } from "../api/client";
import { formatAmount, formatRelativeTime } from "../utils/format";
import type { HumanDecision, RunStatus, PayPalItemStatus } from "../types/api";
import { PolicyBadge, HumanDecisionBadge, AmountCell, RunStatusBadge } from "../components/PolicyBadge";
import styles from "./Review.module.css";

const POLL_INTERVAL = 3000;
const EXECUTING_STATUSES: RunStatus[] = ["EXECUTING"];

export function Review() {
  const { id } = useParams<{ id: string }>();
  const runId = Number(id);
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [expandedRows, setExpandedRows] = useState<Set<number>>(new Set());
  const [confirmExecute, setConfirmExecute] = useState(false);
  const [lastPolled, setLastPolled] = useState<Date | null>(null);

  const { data: run, isLoading: runLoading, error: runError, refetch: refetchRun } = useQuery({
    queryKey: queryKeys.run(runId),
    queryFn: () => api.getRun(runId),
    enabled: !!runId,
  });

  const { data: audit, isLoading: auditLoading } = useQuery({
    queryKey: queryKeys.auditSummary(runId),
    queryFn: () => api.getAuditSummary(runId),
    enabled: !!runId,
  });

  const { data: items = [], isLoading: itemsLoading } = useQuery({
    queryKey: queryKeys.runItems(runId),
    queryFn: () => api.getRunItems(runId),
    enabled: !!runId,
  });

  // Poll while executing
  useEffect(() => {
    if (!run || !EXECUTING_STATUSES.includes(run.status)) return;

    const interval = setInterval(() => {
      refetchRun();
      setLastPolled(new Date());
    }, POLL_INTERVAL);

    return () => clearInterval(interval);
  }, [run?.status, refetchRun]);

  const setDecisionMutation = useMutation({
    mutationFn: ({ itemId, decision }: { itemId: number; decision: HumanDecision }) =>
      api.setItemDecision(runId, itemId, decision),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.runItems(runId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.run(runId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.auditSummary(runId) });
    },
  });

  const approveAllMutation = useMutation({
    mutationFn: () => api.approveAllPending(runId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.runItems(runId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.run(runId) });
    },
  });

  const executeMutation = useMutation({
    mutationFn: () => api.executeRun(runId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.run(runId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.runItems(runId) });
      setConfirmExecute(false);
    },
  });

  const toggleRow = useCallback((itemId: number) => {
    setExpandedRows((prev) => {
      const next = new Set(prev);
      if (next.has(itemId)) next.delete(itemId);
      else next.add(itemId);
      return next;
    });
  }, []);

  const needsReviewItems = items.filter((i) => i.policy_decision === "NEEDS_REVIEW");
  const blockedItems = items.filter((i) => i.policy_decision === "BLOCKED");
  const pendingHumanDecision = items.filter(
    (i) => i.policy_decision !== "BLOCKED" && i.human_decision === "PENDING"
  );
  const approvedItems = items.filter(
    (i) => i.human_decision === "APPROVED" && i.policy_decision !== "BLOCKED"
  );
  const totalApprovedAmount = approvedItems.reduce((sum, i) => sum + Number(i.amount), 0);

  const canExecute =
    run?.status === "REVIEW" && pendingHumanDecision.length === 0 && approvedItems.length > 0;

  if (runLoading || itemsLoading || auditLoading) {
    return <div className={styles.loading}>Loading run details...</div>;
  }

  if (runError || !run) {
    return (
      <div className={styles.error}>
        <h2>Run not found</h2>
        <button onClick={() => navigate("/")} className={styles.backBtn}>
          Back to New Run
        </button>
      </div>
    );
  }

  const isExecuting = run.status === "EXECUTING";
  const isTerminal = ["COMPLETED", "FAILED", "PARTIAL"].includes(run.status);

  return (
    <div className={styles.container}>
      <header className={styles.header}>
        <div className={styles.headerLeft}>
          <RunStatusBadge status={run.status} />
          <h1 className={styles.title}>Review Payouts</h1>
        </div>
        <div className={styles.headerRight}>
          <span className={styles.senderId}>Batch: {run.sender_batch_id}</span>
        </div>
      </header>

      {/* Budget Progress */}
      <section className={styles.budgetSection} aria-label="Budget overview">
        <div className={styles.budgetHeader}>
          <div>
            <span className={styles.budgetLabel}>Budget</span>
            <span className={styles.budgetValue}>
              {formatAmount(run.budget_cap || "0")} / {formatAmount(audit?.total_amount || "0")}
            </span>
          </div>
          <div className={styles.counts}>
            <span className={`${styles.count} ${styles.approved}`}>
              <span className={styles.countIcon} aria-hidden="true">✓</span>
              {audit?.auto_approved ?? 0} auto-approved
            </span>
            <span className={`${styles.count} ${styles.review}`}>
              <span className={styles.countIcon} aria-hidden="true">⚠</span>
              {audit?.needs_review ?? 0} need review
            </span>
            <span className={`${styles.count} ${styles.blocked}`}>
              <span className={styles.countIcon} aria-hidden="true">✕</span>
              {audit?.blocked ?? 0} blocked
            </span>
          </div>
        </div>
        {run.budget_cap && (
          <div className={styles.progressBar} role="progressbar" aria-valuenow={Math.min(100, (Number(audit?.total_amount || "0") / Number(run.budget_cap)) * 100)} aria-valuemin={0} aria-valuemax={100} aria-label="Budget usage">
            <div
              className={`${styles.progressFill} ${Number(audit?.total_amount || "0") > Number(run.budget_cap) ? styles.overBudget : ""}`}
              style={{ width: `${Math.min(100, (Number(audit?.total_amount || "0") / Number(run.budget_cap)) * 100)}%` }}
            />
          </div>
        )}
      </section>

      {/* Items Table */}
      <section className={styles.tableSection} aria-label="Payout items">
        <div className={styles.tableWrapper}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th scope="col">Name</th>
                <th scope="col">Email</th>
                <th scope="col">Amount</th>
                <th scope="col">Note</th>
                <th scope="col">Policy Decision</th>
                <th scope="col">Your Decision</th>
                <th scope="col">PayPal Status</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => {
                return [
                    <tr
                      key={`${item.id}-main`}
                    className={`${styles.row} ${expandedRows.has(item.id) ? styles.expanded : ""}`}
                    onClick={() => toggleRow(item.id)}
                    style={{ cursor: item.ai_flags || item.policy_reasons ? "pointer" : "default" }}
                  >
                  <td className={styles.cellName}>
                    <span className={styles.name}>{item.name}</span>
                  </td>
                  <td className={styles.cellEmail}>{item.email || <span className={styles.missingEmail}>No email</span>}</td>
                  <td className={styles.cellAmount}>
                    <AmountCell amount={item.amount} currency={item.currency} />
                  </td>
                  <td className={styles.cellNote}>{item.note || <span className={styles.emptyNote}>—</span>}</td>
                  <td className={styles.cellPolicy}>
                    <PolicyBadge decision={item.policy_decision} size="md" />
                  </td>
                  <td className={styles.cellHuman}>
                    <HumanDecisionBadge decision={item.human_decision} size="md" />
                  </td>
                  <td className={styles.cellPaypal}>
                    {isExecuting || isTerminal ? (
                      <span className={`${styles.statusBadge} ${styles[getPayPalStatusVariant(item.paypal_item_status)]}`}>
                        {getPayPalStatusLabel(item.paypal_item_status)}
                      </span>
                    ) : (
                      <span className={styles.notStarted}>Not sent</span>
)}
                  </td>
                </tr>,
                    expandedRows.has(item.id) && (
                      <tr
                        key={`${item.id}-expanded`}
                        className={styles.expandedRow}
                      >
                        <td colSpan={7}>
                          <div className={styles.expandedContent}>
                            <div className={styles.expandedSection}>
                              <h4 className={styles.expandedTitle}>AI Explanation</h4>
                              <p className={styles.expandedText}>{item.ai_flags?.explanation || "No AI explanation available."}</p>
                              {item.ai_flags?.flags.length && (
                                <ul className={styles.flagsList}>
                                  {item.ai_flags.flags.map((flag, idx) => (
                                    <li key={idx} className={styles.flagItem}>
                                      <span className={styles.flagType}>{flag.type}:</span> {flag.message}
                                    </li>
                                  ))}
                                </ul>
                              )}
                            </div>
                            {item.policy_reasons && item.policy_reasons.length > 0 && (
                              <div className={styles.expandedSection}>
                                <h4 className={styles.expandedTitle}>Rules Triggered</h4>
                                <ul className={styles.policyReasonsList}>
                                  {item.policy_reasons.map((reason, idx) => (
                                    <li key={idx} className={`${styles.policyReason} ${styles[reason.severity.toLowerCase()]}`}>
                                      <span className={styles.reasonCode}>{reason.code}</span>
                                      <span className={styles.reasonMessage}>{reason.message}</span>
                                    </li>
                                  ))}
                                </ul>
                              </div>
                            )}
                          </div>
                        </td>
                      </tr>
                    )
                  ];
              })}
            </tbody>
          </table>
        </div>
        {items.length === 0 && (
          <div className={styles.emptyState}>
            <p>No payout items in this run.</p>
          </div>
        )}
      </section>

      {/* Bulk Actions */}
      <div className={styles.bulkActions}>
        <button
          onClick={() => approveAllMutation.mutate()}
          disabled={approveAllMutation.isPending || needsReviewItems.length === 0}
          className={styles.bulkBtn}
        >
          Approve All Safe Items ({needsReviewItems.length})
        </button>
        <button
          onClick={() => {
            blockedItems.forEach((item) => setDecisionMutation.mutate({ itemId: item.id, decision: "REJECTED" }));
          }}
          disabled={setDecisionMutation.isPending || blockedItems.length === 0}
          className={`${styles.bulkBtn} ${styles.danger}`}
        >
          Reject All Blocked ({blockedItems.length})
        </button>
      </div>

      {/* Execute / Sticky Footer */}
      <footer className={styles.stickyFooter}>
        <div className={styles.footerContent}>
          <div className={styles.footerSummary}>
            <span>Send <strong>{approvedItems.length}</strong> payouts</span>
            <span className={styles.footerTotal}>
              totaling <strong>{formatAmount(totalApprovedAmount.toFixed(2))}</strong>
            </span>
          </div>
          <div className={styles.footerActions}>
            {isExecuting ? (
              <button className={styles.executingBtn} disabled>
                <span className={styles.spinner} aria-hidden="true"></span>
                Processing... <span className={styles.liveIndicator} aria-live="polite">Live</span>
                {lastPolled && <span className={styles.lastUpdated}>Updated {formatRelativeTime(lastPolled.toISOString())}</span>}
              </button>
            ) : isTerminal ? (
              <button className={styles.doneBtn} disabled>
                {run.status === "COMPLETED" ? "Completed" : run.status === "FAILED" ? "Failed" : "Partial"}
              </button>
            ) : (
              <>
                <button
                  onClick={() => setConfirmExecute(true)}
                  disabled={!canExecute}
                  className={styles.executeBtn}
                >
                  Send Payouts
                </button>
                {pendingHumanDecision.length > 0 && (
                  <span className={styles.pendingWarning}>
                    {pendingHumanDecision.length} item(s) need your decision
                  </span>
                )}
              </>
            )}
          </div>
        </div>
      </footer>

      {/* Confirm Execute Modal */}
      {confirmExecute && (
        <div className={styles.modalOverlay} onClick={() => setConfirmExecute(false)} role="dialog" aria-modal="true" aria-labelledby="modal-title">
          <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
            <header className={styles.modalHeader}>
              <h2 id="modal-title" className={styles.modalTitle}>Confirm Payout Execution</h2>
              <button onClick={() => setConfirmExecute(false)} className={styles.modalClose} aria-label="Close">✕</button>
            </header>
            <div className={styles.modalBody}>
              <div className={styles.warningBox}>
                <span className={styles.warningIcon} aria-hidden="true">⚠</span>
                <p>This will send <strong>{approvedItems.length} payouts totaling {formatAmount(totalApprovedAmount.toFixed(2))}</strong> via PayPal Sandbox. This action cannot be undone.</p>
              </div>
              <ul className={styles.recipientList}>
                {approvedItems.slice(0, 5).map((item) => (
                  <li key={item.id} className={styles.recipientItem}>
                    <span>{item.name} ({item.email})</span>
                    <span className={styles.recipientAmount}>{formatAmount(item.amount, item.currency)}</span>
                  </li>
                ))}
                {approvedItems.length > 5 && (
                  <li className={styles.recipientMore}>+{approvedItems.length - 5} more recipients</li>
                )}
              </ul>
            </div>
            <footer className={styles.modalFooter}>
              <button onClick={() => setConfirmExecute(false)} className={styles.modalCancel}>
                Cancel
              </button>
              <button
                onClick={() => {
                  executeMutation.mutate();
                }}
                disabled={executeMutation.isPending}
                className={styles.modalConfirm}
              >
                {executeMutation.isPending ? "Sending..." : "Yes, Send Payouts"}
              </button>
            </footer>
          </div>
        </div>
      )}
    </div>
  );
}

function getPayPalStatusLabel(status: PayPalItemStatus): string {
  const labels: Record<PayPalItemStatus, string> = {
    PENDING: "Queued",
    SUCCESS: "Sent",
    FAILED: "Failed",
    UNCLAIMED: "Unclaimed",
    BLOCKED: "Blocked",
    REFUNDED: "Refunded",
    REVERSED: "Reversed",
  };
  return labels[status] || status;
}

function getPayPalStatusVariant(status: PayPalItemStatus): string {
  const variants: Record<PayPalItemStatus, string> = {
    PENDING: "pending",
    SUCCESS: "success",
    FAILED: "failed",
    UNCLAIMED: "unclaimed",
    BLOCKED: "blocked",
    REFUNDED: "refunded",
    REVERSED: "reversed",
  };
  return variants[status] || "pending";
}