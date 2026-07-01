export default function StatusChip({ children, tone = "neutral" }) {
  return <span className={`hud-status-chip ${tone}`}>{children}</span>;
}
