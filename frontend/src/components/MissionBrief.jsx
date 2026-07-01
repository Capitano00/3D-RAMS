import { ClipboardList } from "lucide-react";
import { formatLatLon, hasValidCoordinate } from "../lib/coordinates";
import { toList } from "../lib/uiState";
import EmptyState from "./EmptyState";
import HudPanel from "./HudPanel";

export default function MissionBrief({ location, briefing, goal }) {
  const hasBriefing = briefing?.headline || toList(briefing?.priority_checks).length || toList(briefing?.limitations).length;

  return (
    <HudPanel title="Mission Brief" eyebrow="Site context" icon={ClipboardList}>
      <div className="mission-brief">
        <article>
          <span>Site</span>
          <strong>{location?.label || "Unresolved site"}</strong>
          <small>{hasValidCoordinate(location) ? formatLatLon(location.latitude, location.longitude) : "Coordinates pending"}</small>
        </article>
        <article>
          <span>Visit Goal</span>
          <strong>{goal || "Pre-visit review pack"}</strong>
          <small>Human review required before dispatch or work planning.</small>
        </article>
      </div>
      {hasBriefing ? (
        <div className="mission-detail">
          {briefing.headline && <h3>{briefing.headline}</h3>}
          <div className="mission-columns">
            <div>
              <h4>Priority checks</h4>
              <ul>
                {toList(briefing.priority_checks).map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
            <div>
              <h4>Limitations</h4>
              <ul>
                {toList(briefing.limitations).map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
            <div>
              <h4>Next human actions</h4>
              <ul>
                <li>Verify evidence sources and site conditions before dispatch.</li>
                <li>Review low-confidence or fallback items with a competent person.</li>
                <li>Use this pack for pre-visit research only, not approval-to-work.</li>
              </ul>
            </div>
          </div>
        </div>
      ) : (
        <EmptyState title="Brief pending">Ask the agent for a site visit review pack to populate priority checks.</EmptyState>
      )}
    </HudPanel>
  );
}
