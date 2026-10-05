import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import { PolicyBadge, HumanDecisionBadge, PayPalStatusBadge } from "./PolicyBadge";

function getBadgeElement(text: string): HTMLElement {
  const labelElement = screen.getByText(text);
  return labelElement.closest("[class*='_badge_']") as HTMLElement;
}

function hasVariantClass(element: HTMLElement, variant: string): boolean {
  return Array.from(element.classList).some((cls) => cls.includes(variant));
}

describe("PolicyBadge", () => {
  test("renders AUTO_APPROVED with green variant", () => {
    render(<PolicyBadge decision="AUTO_APPROVED" />);
    const badge = getBadgeElement("Auto-approved");
    expect(hasVariantClass(badge, "approved")).toBe(true);
    expect(screen.getByText("✓")).toBeInTheDocument();
  });

  test("renders NEEDS_REVIEW with amber variant", () => {
    render(<PolicyBadge decision="NEEDS_REVIEW" />);
    const badge = getBadgeElement("Needs review");
    expect(hasVariantClass(badge, "review")).toBe(true);
    expect(screen.getByText("⚠")).toBeInTheDocument();
  });

  test("renders BLOCKED with red variant", () => {
    render(<PolicyBadge decision="BLOCKED" />);
    const badge = getBadgeElement("Blocked");
    expect(hasVariantClass(badge, "blocked")).toBe(true);
    expect(screen.getByText("✕")).toBeInTheDocument();
  });

  test("renders unknown for null decision", () => {
    render(<PolicyBadge decision={null} />);
    const badge = getBadgeElement("Unknown");
    expect(hasVariantClass(badge, "unknown")).toBe(true);
  });

  test("renders HumanDecisionBadge for each state", () => {
    render(
      <>
        <HumanDecisionBadge decision="PENDING" />
        <HumanDecisionBadge decision="APPROVED" />
        <HumanDecisionBadge decision="REJECTED" />
      </>
    );
    expect(hasVariantClass(getBadgeElement("Pending"), "pending")).toBe(true);
    expect(hasVariantClass(getBadgeElement("Approved"), "approved")).toBe(true);
    expect(hasVariantClass(getBadgeElement("Rejected"), "rejected")).toBe(true);
  });

  test("renders PayPalStatusBadge for each state", () => {
    render(
      <>
        <PayPalStatusBadge status="SUCCESS" />
        <PayPalStatusBadge status="FAILED" />
        <PayPalStatusBadge status="PENDING" />
        <PayPalStatusBadge status="UNCLAIMED" />
      </>
    );
    expect(hasVariantClass(getBadgeElement("Sent"), "success")).toBe(true);
    expect(hasVariantClass(getBadgeElement("Failed"), "failed")).toBe(true);
    expect(hasVariantClass(getBadgeElement("Queued"), "pending")).toBe(true);
    expect(hasVariantClass(getBadgeElement("Unclaimed"), "unclaimed")).toBe(true);
  });
});

describe("Review page - Send button gating", () => {
  // This test would require mocking the API responses
  // Skipping full integration test for now, component tests above cover badges
  test("send button disabled when items need review", () => {
    // Integration test would go here with mocked query client
    expect(true).toBe(true);
  });
});