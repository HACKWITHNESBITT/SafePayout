// Mock API layer for demo purposes when backend is unavailable
// Enable by setting VITE_USE_MOCK=true
// This implements the same interface as the real API client

import type {
  PayoutRunResponse,
  PayoutRunCreate,
  PayoutItemResponse,
  AuditSummary,
  HumanDecision,
  PolicyDecision,
  PolicyReason,
  ParsedPayee,
  HealthResponse,
} from "../types/api";

const USE_MOCK = import.meta.env.VITE_USE_MOCK === "true";

// Mock delay to simulate network
const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

// In-memory storage
let runs: Map<number, PayoutRunResponse> = new Map();
let items: Map<number, PayoutItemResponse[]> = new Map();
let runCounter = 1;
let itemCounter = 1;

function generateSenderBatchId(): string {
  return `sp_${Math.random().toString(36).substring(2, 15)}`;
}

function generatePayPalBatchId(): string {
  return `batch_${Math.random().toString(36).substring(2, 15)}`;
}

function generatePayPalItemId(): string {
  return `item_${Math.random().toString(36).substring(2, 15)}`;
}

export const mockApi = {
  health: async (): Promise<HealthResponse> => {
    await delay(100);
    return { status: "ok", version: "0.1.0", environment: "development" };
  },

  createRun: async (data: PayoutRunCreate): Promise<PayoutRunResponse> => {
    await delay(300);
    const run: PayoutRunResponse = {
      id: runCounter++,
      status: "DRAFT",
      budget_cap: data.budget_cap ? Number(data.budget_cap).toFixed(2) : null,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      sender_batch_id: generateSenderBatchId(),
      paypal_batch_id: null,
    };
    runs.set(run.id, run);
    items.set(run.id, []);
    return run;
  },

  getRun: async (id: number): Promise<PayoutRunResponse> => {
    await delay(100);
    const run = runs.get(id);
    if (!run) throw new Error("Run not found");
    return run;
  },

  listRuns: async (skip = 0, limit = 50): Promise<PayoutRunResponse[]> => {
    await delay(100);
    const all = Array.from(runs.values()).sort((a, b) => b.id - a.id);
    return all.slice(skip, skip + limit);
  },

  uploadFile: async (runId: number, _file: File): Promise<PayoutRunResponse> => {
    await delay(1500); // Simulate AI parsing + policy evaluation
    
    const run = runs.get(runId);
    if (!run) throw new Error("Run not found");
    
    // Mock parsed payees based on sample data
    const mockPayees: ParsedPayee[] = [
      { name: "Amina Diallo", email: "amina.diallo@example.com", amount: "480.00", currency: "USD", note: "40 hrs at $12/hr" },
      { name: "Brian O'Connor", email: "brian.oconnor@example.com", amount: "300.00", currency: "USD", note: "flat fee" },
      { name: "Carlos Mendez", email: "carlos.mendez@example.com", amount: "1250.00", currency: "USD", note: "project completion" },
      { name: "Amina Diallo", email: "amina.diallo@example.com", amount: "480.00", currency: "USD", note: "duplicate entry" },
      { name: "Diana Prince", email: "diana.prince@invalid-email", amount: "200.00", currency: "USD", note: "malformed email" },
      { name: "Ethan Hunt", email: "ethan.hunt@example.com", amount: "5000.00", currency: "USD", note: "unusually large" },
      { name: "Fiona Gallagher", email: "fiona.g@example.com", amount: "50.00", currency: "USD", note: "small payment" },
      { name: "Grace Hopper", email: "grace.hopper@example.com", amount: "480.00", currency: "USD", note: "40 hrs at $12/hr" },
    ];

    const runItems: PayoutItemResponse[] = mockPayees.map((p, idx) => {
      // Determine policy decision based on mock rules
      let policyDecision: PolicyDecision = "AUTO_APPROVED";
      const reasons: PolicyReason[] = [];
      
      if (p.email === "amina.diallo@example.com" && idx > 0) {
        policyDecision = "BLOCKED";
        reasons.push({ code: "DUPLICATE_PAYEE_IN_RUN", message: "Duplicate payee in this run", severity: "ERROR" });
      } else if (p.email.includes("@invalid-email")) {
        policyDecision = "BLOCKED";
        reasons.push({ code: "INVALID_EMAIL_FORMAT", message: "Invalid email format", severity: "ERROR" });
      } else if (Number(p.amount) > 1000) {
        policyDecision = "NEEDS_REVIEW";
        reasons.push({ code: "AMOUNT_ANOMALY", message: `Amount ${p.amount} is unusual`, severity: "WARNING" });
      }

      const humanDecision: HumanDecision = policyDecision === "AUTO_APPROVED" ? "APPROVED" : "PENDING";

      const item: PayoutItemResponse = {
        id: itemCounter++,
        run_id: runId,
        name: p.name,
        email: p.email,
        amount: p.amount,
        currency: p.currency,
        note: p.note,
        ai_flags: {
          flags: reasons.map(r => ({ type: r.code.toLowerCase().replace(/_/g, "-"), message: r.message })),
          explanation: reasons.length > 0 ? `This payment was flagged because ${reasons[0].message.toLowerCase()}.` : "No issues detected",
        },
        policy_decision: policyDecision,
        policy_reasons: reasons,
        human_decision: humanDecision,
        paypal_item_status: "PENDING",
        paypal_item_id: null,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
      return item;
    });

    items.set(runId, runItems);
    run.status = "REVIEW";
    run.updated_at = new Date().toISOString();
    runs.set(runId, run);
    return run;
  },

  uploadText: async (runId: number, text: string): Promise<PayoutRunResponse> => {
    // Same as uploadFile but with text parsing simulation
    await delay(1500);
    return mockApi.uploadFile(runId, new File([text], "text.txt"));
  },

  getRunItems: async (runId: number): Promise<PayoutItemResponse[]> => {
    await delay(100);
    return items.get(runId) || [];
  },

  setItemDecision: async (runId: number, itemId: number, decision: HumanDecision): Promise<PayoutItemResponse> => {
    await delay(200);
    const runItems = items.get(runId) || [];
    const item = runItems.find(i => i.id === itemId);
    if (!item) throw new Error("Item not found");
    if (item.policy_decision === "BLOCKED" && decision === "APPROVED") {
      throw new Error("Blocked items cannot be approved");
    }
    item.human_decision = decision;
    item.updated_at = new Date().toISOString();
    items.set(runId, runItems);
    return item;
  },

  approveAllPending: async (runId: number): Promise<PayoutRunResponse> => {
    await delay(300);
    const runItems = items.get(runId) || [];
    runItems.forEach(item => {
      if (item.policy_decision === "NEEDS_REVIEW" && item.human_decision === "PENDING") {
        item.human_decision = "APPROVED";
        item.updated_at = new Date().toISOString();
      }
    });
    items.set(runId, runItems);
    const run = runs.get(runId)!;
    run.updated_at = new Date().toISOString();
    runs.set(runId, run);
    return run;
  },

  executeRun: async (runId: number): Promise<PayoutRunResponse> => {
    await delay(2000); // Simulate PayPal API call
    const run = runs.get(runId)!;
    const runItems = items.get(runId) || [];
    
    const approvedItems = runItems.filter(i => i.human_decision === "APPROVED" && i.policy_decision !== "BLOCKED");
    if (approvedItems.length === 0) throw new Error("No approved items to execute");
    
    run.status = "EXECUTING";
    run.paypal_batch_id = generatePayPalBatchId();
    run.updated_at = new Date().toISOString();
    runs.set(runId, run);

    // Simulate async PayPal processing
    setTimeout(() => {
      const updatedRun = runs.get(runId)!;
      const updatedItems = items.get(runId) || [];
      
      updatedItems.forEach(item => {
        if (item.human_decision === "APPROVED" && item.policy_decision !== "BLOCKED") {
          // Randomly assign success/failed for demo
          const success = Math.random() > 0.1;
          item.paypal_item_status = success ? "SUCCESS" : "FAILED";
          item.paypal_item_id = generatePayPalItemId();
          item.updated_at = new Date().toISOString();
        }
      });
      
      const failedCount = updatedItems.filter(i => i.paypal_item_status === "FAILED").length;
      const unclaimedCount = updatedItems.filter(i => i.paypal_item_status === "UNCLAIMED").length;
      
      if (failedCount === 0 && unclaimedCount === 0) {
        updatedRun.status = "COMPLETED";
      } else if (failedCount > 0 && unclaimedCount === 0 && failedCount === updatedItems.filter(i => i.human_decision === "APPROVED").length) {
        updatedRun.status = "FAILED";
      } else {
        updatedRun.status = "PARTIAL";
      }
      updatedRun.updated_at = new Date().toISOString();
      runs.set(runId, updatedRun);
      items.set(runId, updatedItems);
    }, 3000);

    return run;
  },

  getAuditSummary: async (runId: number): Promise<AuditSummary> => {
    await delay(100);
    const run = runs.get(runId)!;
    const runItems = items.get(runId) || [];
    
    const totalAmount = runItems.reduce((sum, i) => sum + Number(i.amount), 0).toFixed(2);
    const autoApproved = runItems.filter(i => i.policy_decision === "AUTO_APPROVED").length;
    const needsReview = runItems.filter(i => i.policy_decision === "NEEDS_REVIEW").length;
    const blocked = runItems.filter(i => i.policy_decision === "BLOCKED").length;
    const humanApproved = runItems.filter(i => i.human_decision === "APPROVED").length;
    const humanRejected = runItems.filter(i => i.human_decision === "REJECTED").length;
    
    return {
      run_id: run.id,
      run_status: run.status,
      total_items: runItems.length,
      auto_approved: autoApproved,
      needs_review: needsReview,
      blocked: blocked,
      human_approved: humanApproved,
      human_rejected: humanRejected,
      total_amount: totalAmount,
      budget_cap: run.budget_cap,
      paypal_batch_id: run.paypal_batch_id,
      items: runItems,
      events: [
        { id: 1, run_id: run.id, type: "run.created", detail: { item_count: runItems.length }, created_at: run.created_at },
        ...(run.status !== "DRAFT" && run.status !== "REVIEW" ? [{
          id: 2, run_id: run.id, type: "run.executed", detail: { payout_batch_id: run.paypal_batch_id }, created_at: new Date().toISOString()
        }] : []),
      ],
    };
  },
};

// Wrapper that uses mock or real API based on env
export const api = USE_MOCK ? mockApi : (await import("./client")).api;