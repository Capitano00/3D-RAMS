import { Database } from "lucide-react";
import { toList } from "../lib/uiState";
import ConfidenceBadge from "./ConfidenceBadge";
import EmptyState from "./EmptyState";
import HudPanel from "./HudPanel";

export default function EvidenceLedger({ evidence }) {
  return (
    <HudPanel title="Evidence Ledger" eyebrow="Inspectable sources" icon={Database}>
      {toList(evidence).length ? (
        <div className="evidence-ledger">
          {toList(evidence).map((item) => (
            <article className="ledger-row" key={item.id}>
              <div>
                <strong>{item.title}</strong>
                <ConfidenceBadge value={item.status || item.confidence || "review"} />
              </div>
              <span>{item.source || "Source pending"}</span>
              <p>{item.why_it_matters || item.summary || "Evidence item available for human review."}</p>
            </article>
          ))}
        </div>
      ) : (
        <EmptyState title="No evidence yet">Evidence items appear after the agent completes a site run.</EmptyState>
      )}
    </HudPanel>
  );
}
