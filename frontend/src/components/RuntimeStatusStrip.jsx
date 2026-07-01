import { Cloud } from "lucide-react";
import HudPanel from "./HudPanel";
import StatusChip from "./StatusChip";

function fallbackTone(runtime) {
  if (runtime?.fallback?.status || runtime?.fallbackReason) return "fallback";
  if (runtime?.briefingMode === "fallback") return "fallback";
  return "neutral";
}

export default function RuntimeStatusStrip({ runtime, safety, accessLabel }) {
  return (
    <HudPanel title="Runtime Status" eyebrow="System state" icon={Cloud}>
      <div className="runtime-hud-strip">
        <article>
          <span>Agent Mode</span>
          <strong>{runtime?.activeAgentMode || runtime?.agentMode || "not run"}</strong>
        </article>
        <article>
          <span>Briefing</span>
          <strong>{runtime?.briefingMode || "not run"}</strong>
        </article>
        <article>
          <span>Safety</span>
          <strong>{safety?.level || "ready"}</strong>
        </article>
        <article>
          <span>Fallback</span>
          <StatusChip tone={fallbackTone(runtime)}>{fallbackTone(runtime) === "fallback" ? "visible" : "none flagged"}</StatusChip>
        </article>
        <article>
          <span>Session</span>
          <strong>{accessLabel || runtime?.sessionTraceMode || "local"}</strong>
        </article>
      </div>
    </HudPanel>
  );
}
