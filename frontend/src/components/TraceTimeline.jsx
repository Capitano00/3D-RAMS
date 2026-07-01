import { GitBranch } from "lucide-react";
import { toList } from "../lib/uiState";
import EmptyState from "./EmptyState";
import HudPanel from "./HudPanel";
import StatusChip from "./StatusChip";

export default function TraceTimeline({ trace }) {
  return (
    <HudPanel title="Trace Timeline" eyebrow="Agent workflow" icon={GitBranch}>
      {toList(trace).length ? (
        <div className="trace-timeline">
          {toList(trace).map((step, index) => (
            <article className="trace-step" key={`${step.name}-${index}`}>
              <span>{String(index + 1).padStart(2, "0")}</span>
              <div>
                <div>
                  <strong>{step.name}</strong>
                  <StatusChip tone={step.status || "neutral"}>{step.status || "unknown"}</StatusChip>
                </div>
                <p>{step.summary}</p>
                {step.fallbackReason && <small>{step.fallbackReason}</small>}
              </div>
            </article>
          ))}
        </div>
      ) : (
        <EmptyState title="No trace yet">Tool timeline appears after the agent runs.</EmptyState>
      )}
    </HudPanel>
  );
}
