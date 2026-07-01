import { Radar } from "lucide-react";
import DomainCard from "./DomainCard";
import EmptyState from "./EmptyState";
import HudPanel from "./HudPanel";

export default function ResearchCoverageGrid({ coverage }) {
  return (
    <HudPanel title="Research Coverage" eyebrow="Pre-visit domains" icon={Radar}>
      {coverage?.length ? (
        <div className="domain-grid">
          {coverage.map((domain) => (
            <DomainCard domain={domain} key={domain.id} />
          ))}
        </div>
      ) : (
        <EmptyState title="No research domains yet">
          Run the agent to estimate weather, terrain, access, infrastructure, utilities, water, planning, hazards,
          evidence quality, and safety-gate coverage.
        </EmptyState>
      )}
    </HudPanel>
  );
}
