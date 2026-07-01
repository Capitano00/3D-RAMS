import { Gauge } from "lucide-react";
import HudPanel from "./HudPanel";
import StatusChip from "./StatusChip";

export default function ImpactSummary({ metrics }) {
  const coveredDomains = metrics.coveredDomains || 0;
  const totalDomains = metrics.totalDomains || 0;

  return (
    <HudPanel
      title="Pre-visit research pack generated"
      eyebrow="Operational value"
      icon={Gauge}
      rightSlot={<StatusChip tone="neutral">Human review required</StatusChip>}
      className="impact-summary"
    >
      <div className="impact-copy">
        <strong>Save time. Reduce blind spots. Support safer site decisions.</strong>
        <p>
          Weather, terrain, infrastructure, access, planning, evidence, and safety signals are collected into one
          inspectable review pack. Designed to reduce manual research time and expose unknown risks earlier.
        </p>
      </div>
      <div className="impact-metrics">
        <article>
          <span>Evidence</span>
          <strong>{metrics.evidence}</strong>
        </article>
        <article>
          <span>Tool Steps</span>
          <strong>{metrics.trace}</strong>
        </article>
        <article>
          <span>Hazards</span>
          <strong>{metrics.hazards}</strong>
        </article>
        <article>
          <span>Fallback / Low Conf.</span>
          <strong>{metrics.fallbackLowConfidence}</strong>
        </article>
        <article>
          <span>Domains Covered</span>
          <strong>
            {coveredDomains}/{totalDomains}
          </strong>
        </article>
      </div>
    </HudPanel>
  );
}
