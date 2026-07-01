import StatusChip from "./StatusChip";

function toneForConfidence(value) {
  const normalized = String(value || "").toLowerCase();
  if (normalized.includes("low")) return "low";
  if (normalized.includes("high") || normalized.includes("ready") || normalized.includes("available")) return "high";
  if (normalized.includes("fallback")) return "fallback";
  if (normalized.includes("missing")) return "missing";
  return "neutral";
}

export default function ConfidenceBadge({ value }) {
  return <StatusChip tone={toneForConfidence(value)}>{value || "review"}</StatusChip>;
}
