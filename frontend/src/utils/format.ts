// Decimal-safe money formatting - never use float math on amounts
// Amounts from API come as strings, display via Intl.NumberFormat

export function formatAmount(amount: string, currency = "USD"): string {
  const num = Number(amount);
  if (Number.isNaN(num)) return amount;
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(num);
}

export function formatAmountPlain(amount: string): string {
  const num = Number(amount);
  if (Number.isNaN(num)) return amount;
  return new Intl.NumberFormat("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(num);
}

export function sumAmounts(amounts: string[]): string {
  const total = amounts.reduce((sum, amt) => sum + Number(amt), 0);
  return total.toFixed(2);
}

export function formatDateTime(isoString: string): string {
  return new Date(isoString).toLocaleString("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

export function formatRelativeTime(isoString: string): string {
  const date = new Date(isoString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSecs = Math.floor(diffMs / 1000);
  const diffMins = Math.floor(diffSecs / 60);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffSecs < 60) return "just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}