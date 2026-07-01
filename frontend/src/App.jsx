import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  Bot,
  Clock3,
  Cloud,
  Compass,
  FileUp,
  GitBranch,
  KeyRound,
  Layers,
  MapPinned,
  Route,
  Search,
  Send,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import SceneViewer from "./components/SceneViewer";
import ImpactSummary from "./components/ImpactSummary";
import MissionBrief from "./components/MissionBrief";
import ResearchCoverageGrid from "./components/ResearchCoverageGrid";
import SafetyBoundaryRail from "./components/SafetyBoundaryRail";
import { AGENT_WORKFLOW_STEPS, OPERATIONAL_SOURCE_GROUPS } from "./data/operationalSources";
import {
  countEvidenceItems,
  countFallbackItems,
  countHazards,
  countLowConfidenceItems,
  countTraceSteps,
  estimateResearchCoverage,
} from "./lib/resultMetrics";
import {
  getAnnotations,
  getBriefing,
  getEvidence,
  getHazards,
  getLocation,
  getRuntime,
  getSafety,
  getScene,
  getTrace,
  toList,
} from "./lib/uiState";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";
const STARTER_PROMPT =
  "I want to visit 8 Albert Embankment tomorrow for a survey. Please prepare a pre-visit review pack covering access, weather, nearby infrastructure, utilities, terrain/context, surrounding risks, evidence, and safety limitations.";

const RISK_GROUPS = [
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

function AccessPanel({ onStart, loading }) {
  const [accessCode, setAccessCode] = useState("");
  const [testerAlias, setTesterAlias] = useState(localStorage.getItem("3drams-tester-alias") || "");

  async function submit(event) {
    event.preventDefault();
    localStorage.setItem("3drams-tester-alias", testerAlias);
    onStart({ accessCode, testerAlias });
  }

  return (
    <section className="access-panel">
      <div>
        <p className="eyebrow">Hosted Agent MVP</p>
        <h1>3D-RAMS Pre-Visit Agent</h1>
        <p>
          Enter the test access code, then ask for a site-visit risk briefing in normal language.
          Bedrock access stays server-side.
        </p>
      </div>
      <form onSubmit={submit}>
        <label>
          Access code
          <input
            value={accessCode}
            onChange={(event) => setAccessCode(event.target.value)}
            placeholder="Leave blank for local dev"
            type="password"
          />
        </label>
        <label>
          Tester alias
          <input
            value={testerAlias}
            onChange={(event) => setTesterAlias(event.target.value)}
            placeholder="Optional, e.g. teammate-a"
          />
        </label>
        <button disabled={loading}>
          <KeyRound size={16} />
          {loading ? "Starting" : "Start test session"}
        </button>
      </form>
    </section>
  );
}

function ChatPanel({ messages, prompt, setPrompt, onSend, loading, uploads, onMockUpload }) {
  return (
    <section className="agent-chat panel">
      <div className="panel-heading">
        <Bot size={18} />
        <div>
          <h2>FieldBrief Agent</h2>
          <p>Ask in normal language. The agent may clarify, then returns a review pack with evidence and trace.</p>
        </div>
      </div>
      <div className="chat-guidance" aria-label="Chat workflow">
        <span>User request</span>
        <span>Clarifying questions</span>
        <span>3D review pack</span>
      </div>
      <div className="message-list">
        {messages.map((message) => (
          <article className={`message ${message.role}`} key={message.id}>
            <span>{message.role === "user" ? "You" : "3D-RAMS Agent"}</span>
            <p>{message.text}</p>
            {message.questions?.length > 0 && (
              <ul>
                {message.questions.map((question) => (
                  <li key={question}>{question}</li>
                ))}
              </ul>
            )}
          </article>
        ))}
      </div>
      <div className="upload-strip">
        <button className="secondary" type="button" onClick={onMockUpload}>
          <FileUp size={16} />
          Register test PDF/image
        </button>
        <span>{uploads.length ? `${uploads.length} evidence file(s) registered` : "Uploads use S3 when hosted; local mode registers metadata only."}</span>
      </div>
      <form className="composer" onSubmit={onSend}>
        <textarea
          aria-label="Site visit request"
          value={prompt}
          onChange={(event) => setPrompt(event.target.value)}
          placeholder="Describe the site visit, activity, date, and any known constraints."
        />
        <button disabled={loading || !prompt.trim()}>
          <Send size={16} />
          {loading ? "Running" : "Send"}
        </button>
      </form>
    </section>
  );
}

function RiskCards({ hazards, briefing }) {
  const items = toList(hazards).slice(0, 6);
  const grouped = RISK_GROUPS.map((group) => ({
    ...group,
    hazards: items.filter((hazard) => classifyHazard(hazard) === group.id),
  }));

  return (
    <section className="panel">
      <div className="panel-heading">
        <AlertTriangle size={18} />
        <div>
          <h2>Risk Review</h2>
          <p>Candidate findings grouped for human verification before dispatch.</p>
        </div>
      </div>
      <div className="risk-grid">
        {items.length ? (
          grouped.map((group) => (
            <section className="risk-group" key={group.id}>
              <div className="risk-group-heading">
                <h3>{group.label}</h3>
                <span>{group.hazards.length}</span>
              </div>
              <div className="risk-group-list">
                {group.hazards.length ? (
                  group.hazards.map((hazard) => (
                    <article key={hazard.id || hazard.title}>
                      <strong>{hazard.title}</strong>
                      <em className={`status ${hazard.confidence || "warning"}`}>{hazard.confidence || "review"}</em>
                      <p>{hazard.reason || hazard.summary || "Review this item before the site visit."}</p>
                    </article>
                  ))
                ) : (
                  <p className="empty-copy">No items currently grouped here.</p>
                )}
              </div>
            </section>
          ))
        ) : (
          <p className="empty-copy">Risk cards appear after the agent runs tools.</p>
        )}
      </div>
      {briefing && (
        <div className="briefing-block">
          <h3>{briefing.headline}</h3>
          <ul>
            {toList(briefing.priority_checks).map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

function EvidenceAndTrace({ evidence, trace, safety, runtime }) {
  return (
    <section className="panel evidence-trace">
      <div className="panel-heading">
        <GitBranch size={18} />
        <h2>Evidence, Trace + Safety</h2>
      </div>
      <div className="runtime-strip">
        <article>
          <span>Mode</span>
          <strong>{runtime?.activeAgentMode || "not run"}</strong>
        </article>
        <article>
          <span>Briefing</span>
          <strong>{runtime?.briefingMode || "not run"}</strong>
        </article>
        <article>
          <span>Safety</span>
          <strong>{safety?.level || "not run"}</strong>
        </article>
      </div>
      <div className="evidence-trace-grid">
        <div>
          <h3>Evidence Register</h3>
          {toList(evidence).length ? (
            toList(evidence).map((item) => (
              <article className="compact-row" key={item.id || item.title}>
                <strong>{item.title}</strong>
                <span>{item.source || "Source pending"}</span>
                <p>{item.why_it_matters || item.summary || "Evidence item available for human review."}</p>
                <small>{item.status || item.confidence || "review"}</small>
              </article>
            ))
          ) : (
            <p className="empty-copy">Evidence items appear after the agent completes a site run.</p>
          )}
        </div>
        <div>
          <h3>Tool Timeline</h3>
          {toList(trace).map((step, index) => (
            <article className="compact-row trace" key={`${step.name}-${index}`}>
              <strong>{String(index + 1).padStart(2, "0")} · {step.name}</strong>
              <span>{step.summary}</span>
              <small>{step.status}</small>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

function WorkflowBridge({ location, metrics, runtime, uploads }) {
  const resolvedLabel = location?.label || "Waiting for resolved site";
  const generatedItems = metrics.evidence + metrics.trace + metrics.hazards;

  return (
    <section className="workflow-bridge" aria-label="ASI intake to enterprise review workflow">
      <article className="bridge-card bridge-card-primary">
        <div className="bridge-heading">
          <Sparkles size={18} />
          <span>Fetch / ASI:One entry</span>
        </div>
        <h2>Ask with a coordinate, place name, address, or incomplete site prompt.</h2>
        <p>
          The agent resolves what it can, asks only for missing critical details, then generates a
          small-area pre-visit review pack for human checking.
        </p>
        <div className="prompt-example">
          I need to visit 8 Albert Embankment and land to the rear tomorrow. What should I know before going?
        </div>
      </article>

      <article className="bridge-card">
        <div className="bridge-heading">
          <Search size={18} />
          <span>Ambiguity handling</span>
        </div>
        <div className="bridge-steps">
          <span>Coordinate or place parsing</span>
          <span>Clarifying questions when site/activity is vague</span>
          <span>Fallback and low-confidence labels stay visible</span>
        </div>
      </article>

      <article className="bridge-card">
        <div className="bridge-heading">
          <Layers size={18} />
          <span>3D region model</span>
        </div>
        <div className="bridge-steps">
          <span>Resolved area: {resolvedLabel}</span>
          <span>Boundary highlighted against unrelated surroundings</span>
          <span>Water, access, infrastructure, utility, and hazard layers</span>
        </div>
      </article>

      <article className="bridge-card efficiency-card">
        <div className="bridge-heading">
          <Clock3 size={18} />
          <span>Conduct efficiency proof</span>
        </div>
        <strong>{generatedItems || "No"} review artefact(s) generated</strong>
        <p>
          One agent run turns scattered map, weather, planning, utility, flood, evidence, and trace work
          into a single inspectable pack. Stopwatch baseline can be added for the final demo.
        </p>
        <div className="efficiency-metrics">
          <span>{metrics.coveredDomains}/{metrics.totalDomains} domains</span>
          <span>{uploads.length} upload(s)</span>
          <span>{runtime?.modelCallCount || runtime?.modelCalls?.length || 0} model call(s)</span>
        </div>
      </article>
    </section>
  );
}

function OperationalDataPlan() {
  return (
    <section className="operational-plan panel" aria-label="Operational data and agent workflow">
      <div className="panel-heading">
        <Layers size={18} />
        <div>
          <h2>Operational Data Sources + Agent Workflow</h2>
          <p>Real integrations where available; cached/fallback states remain labelled for audit and human review.</p>
        </div>
      </div>
      <div className="workflow-steps">
        {AGENT_WORKFLOW_STEPS.map((step, index) => (
          <article key={step.id}>
            <span>{String(index + 1).padStart(2, "0")}</span>
            <strong>{step.label}</strong>
            <p>{step.description}</p>
          </article>
        ))}
      </div>
      <div className="source-matrix">
        {OPERATIONAL_SOURCE_GROUPS.map((group) => (
          <article className={`source-card ${group.status}`} key={group.id}>
            <div>
              <strong>{group.label}</strong>
              <em>{group.status.replace("-", " ")}</em>
            </div>
            <span>{group.agent}</span>
            <p>{group.output}</p>
            <ul>
              {group.sources.map((source) => (
                <li key={source}>{source}</li>
              ))}
            </ul>
          </article>
        ))}
      </div>
    </section>
  );
}

function App() {
  const [session, setSession] = useState(null);
  const [messages, setMessages] = useState([
    {
      id: "welcome",
      role: "assistant",
      text: "Tell me where you are going and what kind of site visit you are planning. I will ask for missing critical details, run tools, and return a structured pre-visit review pack for human review.",
    },
  ]);
  const [prompt, setPrompt] = useState(STARTER_PROMPT);
  const [run, setRun] = useState(null);
  const [uploads, setUploads] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const rawUi = run?.uiState || {};
  const ui = {
    location: getLocation(rawUi),
    scene: getScene(rawUi),
    annotations: getAnnotations(rawUi),
    hazards: getHazards(rawUi),
    evidence: getEvidence(rawUi),
    trace: getTrace(rawUi),
    briefing: getBriefing(rawUi),
    safety: getSafety(rawUi),
  };
  const accessLabel = session?.accessLabel || "not started";
  const runtime = getRuntime(run);
  const researchCoverage = useMemo(() => estimateResearchCoverage(rawUi), [rawUi]);
  const resultMetrics = useMemo(
    () => ({
      evidence: countEvidenceItems(ui.evidence),
      trace: countTraceSteps(ui.trace),
      hazards: countHazards(ui.hazards),
      lowConfidence: countLowConfidenceItems(ui.hazards, ui.evidence, ui.trace),
      fallbackLowConfidence: countLowConfidenceItems(ui.hazards, ui.evidence, ui.trace) + countFallbackItems(ui.evidence, ui.trace),
      coveredDomains: researchCoverage.filter((domain) => ["ready", "partial", "fallback", "blocked"].includes(domain.status)).length,
      totalDomains: researchCoverage.length,
    }),
    [researchCoverage, ui.evidence, ui.hazards, ui.trace],
  );
  const safetyTone = ui.safety?.allowed === false ? "blocked" : ui.safety?.level === "needs_input" ? "warning" : "allowed";
  const fallbackLabel = resultMetrics.fallbackLowConfidence ? `${resultMetrics.fallbackLowConfidence} fallback/verify` : "no fallback flagged";

  async function startSession(payload) {
    setLoading(true);
    setError("");
    try {
      const response = await fetch(`${API_BASE_URL}/api/session/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!response.ok) throw new Error(`Session start failed (${response.status})`);
      setSession(await response.json());
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function sendMessage(event) {
    event.preventDefault();
    if (!prompt.trim() || !session) return;
    const userMessage = { id: `user-${Date.now()}`, role: "user", text: prompt.trim() };
    setMessages((current) => [...current, userMessage]);
    setPrompt("");
    setLoading(true);
    setError("");
    try {
      const response = await fetch(`${API_BASE_URL}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sessionId: session.sessionId,
          message: userMessage.text,
          uploadedFileIds: uploads.map((upload) => upload.uploadId),
          useBedrock: true,
        }),
      });
      if (!response.ok) throw new Error(`Agent run failed (${response.status})`);
      const result = await response.json();
      setRun(result);
      setMessages((current) => [
        ...current,
        {
          id: result.runId,
          role: "assistant",
          text: result.assistantMessage,
          questions: result.clarifyingQuestions || [],
        },
      ]);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function registerMockUpload() {
    if (!session) return;
    setLoading(true);
    setError("");
    try {
      const response = await fetch(`${API_BASE_URL}/api/upload-url`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sessionId: session.sessionId,
          filename: `test-evidence-${uploads.length + 1}.pdf`,
          contentType: "application/pdf",
          sizeBytes: 2048,
        }),
      });
      if (!response.ok) throw new Error(`Upload registration failed (${response.status})`);
      const upload = await response.json();
      setUploads((current) => [...current, upload]);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (session) return;
    const cachedAlias = localStorage.getItem("3drams-tester-alias") || "";
    if (import.meta.env.DEV) {
      startSession({ accessCode: "", testerAlias: cachedAlias });
    }
  }, [session]);

  if (!session) {
    return (
      <main className="app-shell">
        {error && <div className="error-banner">{error}</div>}
        <AccessPanel onStart={startSession} loading={loading} />
      </main>
    );
  }

  return (
    <main className="app-shell product-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">3D-RAMS</p>
          <h1>Pre-Visit FieldBrief Agent</h1>
          <p className="topbar-summary">
            Generate an inspectable 3D site research pack from one natural-language request.
          </p>
          <p className="command-value">Save time. Reduce blind spots. Support safer site decisions.</p>
        </div>
        <div className="status-stack">
          <div className="safety-pill pending">
            <KeyRound size={16} />
            <span>Session</span>
            <strong>{accessLabel}</strong>
          </div>
          <div className={`safety-pill ${safetyTone}`}>
            <ShieldCheck size={16} />
            <span>Safety</span>
            <strong>{ui.safety?.level || "ready"}</strong>
          </div>
          <div className="safety-pill pending">
            <Cloud size={16} />
            <span>Agent</span>
            <strong>{runtime.activeAgentMode || runtime.sessionTraceMode || "memory"}</strong>
          </div>
          <div className={`safety-pill ${resultMetrics.fallbackLowConfidence ? "warning" : "allowed"}`}>
            <AlertTriangle size={16} />
            <span>Fallback</span>
            <strong>{fallbackLabel}</strong>
          </div>
        </div>
      </header>

      {error && <div className="error-banner">{error}</div>}

      <WorkflowBridge location={ui.location} metrics={resultMetrics} runtime={runtime} uploads={uploads} />

      <section className="product-grid">
        <ChatPanel
          messages={messages}
          prompt={prompt}
          setPrompt={setPrompt}
          onSend={sendMessage}
          loading={loading}
          uploads={uploads}
          onMockUpload={registerMockUpload}
        />
        <section className="panel map-panel">
          <div className="panel-heading">
            <MapPinned size={18} />
            <div>
              <h2>3D Site Risk Scene</h2>
              <p>Zoomed small-area model with boundary, water/access/utility layers, annotations, confidence, and fallback status.</p>
            </div>
          </div>
          <div className="region-model-strip" aria-label="3D region model layers">
            <span><Compass size={14} /> Boundary locked</span>
            <span><Route size={14} /> Access context</span>
            <span><Layers size={14} /> Water / utility / hazard layers</span>
          </div>
          <SceneViewer scene={ui.scene} annotations={ui.annotations} location={ui.location} />
        </section>
      </section>

      <section className="review-overview" aria-label="Review pack overview">
        <ImpactSummary metrics={resultMetrics} />
        <SafetyBoundaryRail />
      </section>

      <OperationalDataPlan />

      <section className="result-grid">
        <MissionBrief location={ui.location} briefing={ui.briefing} goal={run?.request?.goal} />
        <ResearchCoverageGrid coverage={researchCoverage} />
      </section>

      <section className="legacy-detail-grid" aria-label="Risk, evidence, trace, and safety detail">
        <RiskCards hazards={ui.hazards} briefing={ui.briefing} />
        <EvidenceAndTrace evidence={ui.evidence} trace={ui.trace} safety={ui.safety} runtime={runtime} />
      </section>
    </main>
  );
}

export default App;
