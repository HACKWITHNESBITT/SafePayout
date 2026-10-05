# SafePayout Demo Script (3-minute walkthrough)

## Setup (before recording)
1. Start backend: `uvicorn app.main:app --reload --app-dir backend`
2. Start frontend: `cd frontend && npm run dev`
3. Open frontend at `http://localhost:5173`
4. Have backend API docs open at `http://localhost:8000/docs` for reference

---

## 0:00-0:15 | New Run — Upload CSV
**Action**: Click "Load Sample Data" → shows CSV preview → click "Analyze Payouts"
**Narration**: "SafePayout starts with messy data. One click loads our sample CSV with duplicates, malformed emails, and unusual amounts."
**Show**: Loading progress messages ("Reading your sheet...", "Checking for problems...", "Applying rules...")

---

## 0:15-0:45 | Review — Policy Decisions
**Action**: Page loads at `/runs/:id`
**Narration**: "The LLM parsed 8 payees. The rules engine flagged 3 issues: a duplicate, a malformed email, and an anomaly."
**Point out**:
- Header: status badge "In Review", budget progress bar (green → amber near cap)
- Counts: 4 auto-approved, 2 need review, 2 blocked
- Table rows: color + icon + text for each decision (never color alone)
- Click a flagged row → expands to show AI explanation + rule reasons side by side

---

## 0:45-1:15 | Review — Human Decisions
**Action**: For "Needs review" rows, click "Approve" or "Reject". Click "Approve all safe items" bulk action.
**Narration**: "You're the human in the loop. Each flagged item needs your call. Bulk actions speed up routine approvals."
**Show**: Button states update, pending count decreases.

---

## 1:15-1:45 | Review — Send Payouts
**Action**: Once all non-blocked items have decisions, sticky footer "Send 4 payouts totaling $X" enables. Click → confirmation modal → "Yes, Send Payouts"
**Narration**: "The Send button only enables when every item has a human decision. The modal summarizes recipients, total, and warns this sends real money in PayPal sandbox."
**Show**: Modal with recipient list, total amount, warning text.

---

## 1:45-2:15 | Execution — Live Status
**Action**: Page transitions to execution view. Status badges update in real time: Queued → Processing → Sent/Failed.
**Narration**: "PayPal processes the batch. We poll every 3 seconds. Each item shows its own timeline."
**Show**: Live indicator pulsing, last-updated timestamp, per-item status badges.

---

## 2:15-2:45 | Audit Summary
**Action**: Click "Audit" tab or navigate to audit view
**Narration**: "Full audit trail: AI-written summary at top, then chronological event log. Download as CSV for compliance."
**Show**: AI audit summary, event timeline, "Download audit as CSV" button.

---

## 2:45-3:00 | Principle Recap
**Action**: Point to principle banner at top of every page
**Narration**: "AI proposes. Rules enforce. You approve. PayPal sends. That's SafePayout."

---

## Key Talking Points for Judges
- **Real AI integration**: Anthropic Claude parses messy CSV/text, not just regex
- **Real policy engine**: 8 rule types (duplicates, allowlist, caps, anomalies, budget)
- **Real PayPal integration**: Sandbox payouts with webhook status updates
- **Human-centered**: Every non-blocked item requires explicit approval
- **Audit-first**: Complete trail from input → decision → execution
- **No third-party trademarks in UI**: PayPal named in text only
- **Accessible**: Keyboard nav, focus states, ARIA labels, contrast

---

## Fallback if Backend Unavailable
The frontend includes a typed mock layer (commented in `src/api/client.ts`) that simulates the full flow for demo purposes. Uncomment and set `VITE_USE_MOCK=true` to run without backend.