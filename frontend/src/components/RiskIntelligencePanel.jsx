import { AlertTriangle } from "lucide-react";
import { toList } from "../lib/uiState";
import ConfidenceBadge from "./ConfidenceBadge";
import EmptyState from "./EmptyState";
import HudPanel from "./HudPanel";

const GROUPS = [
  { id: "immediate", label: "Immediate review" },
  { id: "environmental", label: "Environmental / contextual" },
  { id: "infrastructure", label: "Infrastructure / utility" },
  { id: "verification", label: "Low-confidence / needs verification" },
];

function classifyHazard(hazard) {
  const text = `${hazard?.title || ""} ${hazard?.reason || ""} ${hazard?.summary || ""}`.toLowerCase();
  if (hazard?.confidence === "low" || text.includes("low confidence") || text.includes("verify")) return "verification";
  if (/(ohl|overhead|line|cable|utility|utilities|power|rail|bridge|road|infrastructure)/.test(text)) return "infrastructure";
  if (/(weather|flood|water|river|terrain|slope|ground|environment|context)/.test(text)) return "environmental";
  return "immediate";
}

export default function RiskIntelligencePanel({ hazards, briefing }) {
  const grouped = GROUPS.map((group) => ({
    ...group,
    hazards: toList(hazards).filter((hazard) => classifyHazard(hazard) === group.id),
  }));

  return (
    <HudPanel title="Risk Intelligence" eyebrow="Candidate findings" icon={AlertTriangle}>
      {toList(hazards).length ? (
        <div className="risk-intelligence">
          {grouped.map((group) => (
            <section key={group.id}>
              <h3>{group.label}</h3>
              {group.hazards.length ? (
                group.hazards.map((hazard) => (
                  <article className="risk-intel-row" key={hazard.id || hazard.title}>
                    <div>
                      <strong>{hazard.title}</strong>
                      <ConfidenceBadge value={hazard.confidence || "review"} />
                    </div>
                    <p>{hazard.reason || hazard.summary || "Review this item before the site visit."}</p>
                  </article>
                ))
              ) : (
                <p className="hud-muted">No items currently grouped here.</p>
              )}
            </section>
          ))}
        </div>
      ) : (
        <EmptyState title="No hazards yet">Risk cards appear after the agent runs tools.</EmptyState>
      )}
      {briefing?.headline && (
        <div className="briefing-block">
          <h3>{briefing.headline}</h3>
          <ul>
            {toList(briefing.priority_checks).map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      )}
    </HudPanel>
  );
}
