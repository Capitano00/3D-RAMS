import StatusChip from "./StatusChip";

export default function DomainCard({ domain }) {
  return (
    <article className={`domain-card ${domain.status}`}>
      <div>
        <strong>{domain.label}</strong>
        <StatusChip tone={domain.status}>{domain.status}</StatusChip>
      </div>
      <p>{domain.summary}</p>
      <small>{domain.confidenceLabel}</small>
    </article>
  );
}
