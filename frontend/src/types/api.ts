// API types matching backend/app/schemas.py exactly
// Do not invent fields - these must match the real request/response shapes

export type RunStatus =
  | "DRAFT"
  | "REVIEW"
  | "APPROVED"
  | "EXECUTING"
  | "COMPLETED"
  | "PARTIAL"
  | "FAILED";

export type PolicyDecision = "AUTO_APPROVED" | "NEEDS_REVIEW" | "BLOCKED";

export type HumanDecision = "PENDING" | "APPROVED" | "REJECTED";

export type PayPalItemStatus =
  | "PENDING"
  | "SUCCESS"
  | "FAILED"
  | "UNCLAIMED"
  | "BLOCKED"
  | "REFUNDED"
  | "REVERSED";

export interface PayoutRunCreate {
  budget_cap?: string; // Decimal as string
  raw_text?: string;
  raw_csv?: string;
}

export interface PayoutRunResponse {
  id: number;
  status: RunStatus;
  budget_cap: string | null;
  created_at: string; // ISO datetime
  updated_at: string;
  sender_batch_id: string;
  paypal_batch_id: string | null;
}

export interface PayoutItemBase {
  name: string;
  email: string;
  amount: string; // Decimal as string
  currency: string;
  note?: string | null;
}

export interface PayoutItemResponse extends PayoutItemBase {
  id: number;
  run_id: number;
  ai_flags: AIFlags | null;
  policy_decision: PolicyDecision | null;
  policy_reasons: PolicyReason[] | null;
  human_decision: HumanDecision;
  paypal_item_status: PayPalItemStatus;
  paypal_item_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface PayoutItemDecision {
  human_decision: HumanDecision;
}

export interface PolicyReason {
  code: string;
  message: string;
  severity: "INFO" | "WARNING" | "ERROR";
}

export interface AIFlags {
  flags: AIFlag[];
  explanation: string;
}

export interface AIFlag {
  type: string;
  message: string;
}

export interface ParsedPayee {
  name: string;
  email: string;
  amount: string;
  currency: string;
  note?: string | null;
}

export interface ParsedPayouts {
  payees: ParsedPayee[];
  raw_input_summary: string;
}

export interface AuditEventResponse {
  id: number;
  run_id: number;
  type: string;
  detail: Record<string, unknown> | null;
  created_at: string;
}

export interface AuditSummary {
  run_id: number;
  run_status: RunStatus;
  total_items: number;
  auto_approved: number;
  needs_review: number;
  blocked: number;
  human_approved: number;
  human_rejected: number;
  total_amount: string;
  budget_cap: string | null;
  paypal_batch_id: string | null;
  items: PayoutItemResponse[];
  events: AuditEventResponse[];
}

export interface HealthResponse {
  status: string;
  version: string;
  environment: string;
}

export interface AIReviewItem {
  email: string;
  flags: AIFlag[];
  explanation: string;
}

export interface AIReviewResponse {
  items: AIReviewItem[];
  audit_summary: string;
}

// Request types for API calls
export interface UploadFileRequest {
  file: File;
}

export interface UploadTextRequest {
  text: string;
}