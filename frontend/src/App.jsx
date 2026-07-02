import { useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  Bot,
  Cloud,
  FileUp,
  GitBranch,
  MapPinned,
  MessageSquare,
  Radar,
  RotateCcw,
  Send,
  ShieldCheck,
  X,
} from "lucide-react";
import * as Cesium from "cesium";
import "cesium/Build/Cesium/Widgets/widgets.css";
import { sceneModeFrom } from "./sceneContext.js";

const AGENTCORE_URL = import.meta.env.VITE_AGENTCORE_URL || "/agentcore/invocations";
const CLOUD_ENTRY_PROXY_URL = import.meta.env.VITE_CLOUD_ENTRY_PROXY_URL || "";
const USE_LOCAL_ASIONE = import.meta.env.VITE_USE_LOCAL_ASIONE === "true";
const ENTRY_AGENT_URL = USE_LOCAL_ASIONE ? import.meta.env.VITE_LOCAL_ASIONE_URL || AGENTCORE_URL : CLOUD_ENTRY_PROXY_URL;
const REPORT_LOOKUP_URL = USE_LOCAL_ASIONE ? AGENTCORE_URL : ENTRY_AGENT_URL;
const FIELD_BRIEF_LABEL = "Dev FieldBrief ASI Simulation";
const STARTER_PROMPT =
  "I want to visit 8 Albert Embankment tomorrow for a survey within a 2km radius. Please prepare a pre-visit RAMS-style review pack.";
const REPORT_ACCESS_SCHEMA_VERSION = "3d-rams.report-access.v1";
const REPORT_SESSION_STORAGE_KEY = "3d-rams-report-session-id";

const DEFAULT_REQUEST = {
  siteName: "8 Albert Embankment and land to the rear",
  latitude: 51.492099,
  longitude: -0.118712,
  goal: "Pre-visit RAMS scoping pack",
  fixturePack: "public-lambeth-thames",
  includePlanningFixture: true,
  simulateMapFailure: false,
  useBedrock: true,
  additionalRequest: "",
};

function toList(value) {
  return Array.isArray(value) ? value : [];
}

function firstObject(...values) {
  return values.find((value) => value && typeof value === "object" && !Array.isArray(value)) || null;
}

function present(value) {
  return value !== undefined && value !== null && value !== "";
}

function humanizeToken(value) {
  return String(value || "")
    .replace(/[-_]+/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase())
    .trim();
}

function firstText(value) {
  if (typeof value === "string") return value;
  if (value && typeof value === "object") return value.message || value.summary || value.title || value.id || "";
  return "";
}

function listText(value) {
  return toList(value).map(firstText).filter(Boolean);
}

function latestTraceSummary(trace) {
  return [...toList(trace)].reverse().find((step) => firstText(step)) || null;
}

function riskReferenceIds(item) {
  const references = item?.references || {};
  return {
    sourceIds: toList(references.sourceIds).length ? toList(references.sourceIds) : toList(item?.sourceIds),
    evidenceIds: toList(references.evidenceIds).length ? toList(references.evidenceIds) : toList(item?.evidenceIds),
  };
}

function hasRiskReferences(item) {
  const refs = riskReferenceIds(item);
  return refs.sourceIds.length > 0 || refs.evidenceIds.length > 0;
}

function normalizeFallbackRiskItem(item) {
  const refs = riskReferenceIds(item);
  return {
    ...item,
    sourceIds: refs.sourceIds,
    evidenceIds: refs.evidenceIds,
    note: item.note || item.summary || item.description || item.rationale || "Candidate finding requires human review.",
    confidence: item.confidence || "review",
    category: item.category || item.type || "review",
  };
}

function fallbackRiskSources(run, entryResponse) {
  const outputReport = entryResponse?.agentcoreOutput?.structuredReport;
  return [
    ...toList(run?.structuredReport?.findings),
    ...toList(outputReport?.findings),
    ...toList(run?.structuredReport?.visualization?.annotations),
    ...toList(outputReport?.visualization?.annotations),
    ...toList(run?.annotations),
  ];
}

function dedupeRiskItems(items) {
  const seen = new Set();
  return items.filter((item, index) => {
    const key = item.id || item.annotationId || item.title || item.label || item.note || item.summary || `fallback-${index}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function riskItemsFromRun(run, entryResponse) {
  const hazards = toList(run?.hazards);
  if (hazards.length) return hazards;
  return dedupeRiskItems(fallbackRiskSources(run, entryResponse).filter(hasRiskReferences).map(normalizeFallbackRiskItem));
}

function riskReviewNoticeFromRun(run, entryResponse) {
  if (riskItemsFromRun(run, entryResponse).length) return "";
  return fallbackRiskSources(run, entryResponse).length
    ? "Structured report findings were present, but Risk Review only renders candidate findings with source or evidence references."
    : "Risk cards appear after the agent runs tools.";
}

function attachStructuredReport(run, structuredReport, reviewMetadata, output = {}, entryResponse = {}) {
  if (!run) return run;
  const report = firstObject(structuredReport, run.structuredReport, output.structuredReport, entryResponse.agentcoreOutput?.structuredReport);
  const reviewGate = reviewMetadata || run.reviewMetadata || run.reviewGate || report?.reviewGate || null;
  const progress = firstObject(
    output.progress,
    output.progressState,
    output.runProgress,
    run.progress,
    run.progressState,
    entryResponse.progress,
    entryResponse.progressState,
  );
  const locationGate = firstObject(
    output.locationGate,
    output.locationConfirmationGate,
    output.locationConfirmation,
    run.locationGate,
    run.locationConfirmationGate,
    run.locationConfirmation,
    report?.locationGate,
    report?.locationConfirmationGate,
    entryResponse.locationGate,
    entryResponse.locationConfirmationGate,
    entryResponse.locationConfirmation,
  );
  const repairMetadata = firstObject(
    output.repairMetadata,
    output.reportRepair,
    output.groundingRepair,
    run.repairMetadata,
    run.reportRepair,
    run.groundingRepair,
    report?.repairMetadata,
    report?.reportRepair,
    report?.groundingRepair,
  );
  return {
    ...run,
    ...(report ? { structuredReport: report } : {}),
    ...(reviewGate ? { reviewGate, reviewMetadata: reviewGate } : {}),
    ...(progress ? { progress } : {}),
    ...(locationGate ? { locationGate } : {}),
    ...(repairMetadata ? { repairMetadata } : {}),
  };
}

function reviewGateFromRun(run) {
  return run?.reviewMetadata || run?.reviewGate || run?.structuredReport?.reviewGate || null;
}

function reviewToneFromStatus(status) {
  const normalized = String(status || "").toLowerCase();
  if (normalized.includes("block")) return "blocked";
  if (normalized.includes("pass") || normalized.includes("allow")) return "allowed";
  return "warning";
}

function runToUiState(run, entryResponse) {
  const report = reportFromRun(run, entryResponse);
  if (!run && !report) return {};
  return {
    location: run?.location,
    scene: run?.scene || report?.visualization?.scene,
    annotations: run?.annotations || report?.visualization?.annotations,
    hazards: riskItemsFromRun(run, entryResponse),
    riskReviewNotice: riskReviewNoticeFromRun(run, entryResponse),
    evidence: run?.evidence,
    briefing: run?.briefing,
    safety: run?.safety,
    trace: run?.trace || report?.trace,
    structuredReport: report,
  };
}

function reportFromRun(run, entryResponse) {
  return run?.structuredReport || entryResponse?.agentcoreOutput?.structuredReport || null;
}

function contractStateFrom({ run, entryResponse, persistence }) {
  const output = entryResponse?.agentcoreOutput || {};
  const report = reportFromRun(run, entryResponse);
  return {
    entryRouting: normalizeEntryRouting(entryResponse),
    progress: normalizeProgress(progressSource(run, entryResponse, output, report), run, output, report, entryResponse),
    locationGate: normalizeLocationGate(locationGateSource(run, entryResponse, output, report), entryResponse),
    repair: normalizeRepair(repairSource(run, output, report)),
    review: normalizeReview(reviewGateFromRun(run) || output.reviewMetadata || output.reviewGate || report?.reviewGate),
    sceneMode: sceneModeFrom(run, report, persistence, entryResponse),
  };
}

function normalizeEntryRouting(entryResponse) {
  if (!entryResponse) return null;
  const runtime = firstObject(entryResponse.runtimeObservability) || {};
  const route = entryResponse.route || "";
  const status = entryResponse.status || "";
  const confirmationRequired = status === "confirmation_required" || entryResponse.needsConfirmation;
  const toolsStarted = toolsStartedSummary(runtime.toolsStarted);
  return {
    route,
    status: confirmationRequired ? "confirmation_required" : status,
    tone: statusTone(confirmationRequired ? "confirmation_required" : status),
    activeAgentMode: runtime.activeAgentMode || runtime.entryAgentMode || "",
    noToolReason: runtime.noToolReason || "",
    toolsStarted,
  };
}

function toolsStartedSummary(value) {
  if (!present(value)) return "";
  if (typeof value === "boolean") return value ? "Started" : "Not started";
  if (Array.isArray(value)) return value.length ? "Started" : "Not started";
  if (typeof value === "object") return Object.values(value).some(Boolean) ? "Started" : "Not started";
  return "";
}

function progressSource(run, entryResponse, output, report) {
  return firstObject(
    run?.progress,
    run?.progressState,
    output.progress,
    output.progressState,
    output.runProgress,
    entryResponse?.progress,
    entryResponse?.progressState,
    report?.progress,
    report?.progressState,
  );
}

function normalizeProgress(source, run, output, report, entryResponse) {
  const latestStep = latestTraceSummary(run?.trace || report?.trace || entryResponse?.trace);
  const fallback =
    source ||
    (entryResponse?.status
      ? {
          status: entryResponse.status,
          currentStep: entryResponse.needsConfirmation ? "Awaiting operator confirmation" : "Entry intake",
          latestTraceSummary: entryResponse.assistantMessage,
        }
      : null) ||
    (run
      ? {
          status: output.reportStatus || report?.status || "completed",
          currentStep: "Report payload available",
          latestTraceSummary: latestStep?.summary || latestStep?.message || "Supervisor output is loaded.",
        }
      : null);
  if (!fallback) return null;
  const status =
    fallback.status ||
    fallback.runStatus ||
    fallback.state ||
    output.reportStatus ||
    report?.status ||
    (fallback.blocked || fallback.blockedReason ? "blocked" : "") ||
    (fallback.failed || fallback.errorSummary || fallback.error ? "failed" : "") ||
    (fallback.completed || fallback.done ? "completed" : "") ||
    "unknown";
  return {
    status,
    tone: statusTone(status),
    currentStep: fallback.currentStep || fallback.current_step || fallback.step || fallback.phase || latestStep?.name || "",
    summary:
      fallback.latestTraceSummary ||
      fallback.latestStepSummary ||
      fallback.traceSummary ||
      fallback.summary ||
      fallback.message ||
      latestStep?.summary ||
      "",
    completed: firstObject(fallback.completedState, fallback.completion)?.status || fallback.completed || fallback.done,
    failed: fallback.failed || fallback.errorSummary || fallback.error,
    blocked: fallback.blocked || fallback.blockedReason,
    updatedAt: fallback.updatedAt || fallback.updated_at || fallback.timestamp || "",
    modelCallCount: fallback.modelCallCount ?? fallback.modelCalls ?? run?.runtime?.modelCallCount ?? report?.runtime?.modelCallCount,
    fallbackReason: fallback.fallbackReason || run?.runtime?.fallbackReason || report?.runtime?.fallbackReason || "",
  };
}

function locationGateSource(run, entryResponse, output, report) {
  return (
    firstObject(
      run?.locationGate,
      run?.locationConfirmationGate,
      run?.locationConfirmation,
      output.locationGate,
      output.locationConfirmationGate,
      output.locationConfirmation,
      report?.locationGate,
      report?.locationConfirmationGate,
      report?.locationConfirmation,
      entryResponse?.locationGate,
      entryResponse?.locationConfirmationGate,
      entryResponse?.locationConfirmation,
    ) ||
    (entryResponse?.intake?.locationCandidate
      ? {
          status: entryResponse.status,
          candidate: entryResponse.intake.locationCandidate,
          source: entryResponse.intakeMode || entryResponse.mode || "entry intake",
          reason: entryResponse.confirmation?.summary,
          requiresOperatorConfirmation: entryResponse.status === "confirmation_required" || entryResponse.needsConfirmation,
        }
      : null)
  );
}

function normalizeLocationGate(source, entryResponse) {
  if (!source) return null;
  const candidate = firstObject(source.candidate, source.locationCandidate, source.selectedCandidate) || {};
  return {
    status: source.status || source.state || entryResponse?.status || "available",
    tone: statusTone(source.status || source.state || entryResponse?.status),
    candidateLabel: candidate.label || candidate.name || source.candidateLabel || source.label || source.name || "",
    source: candidate.source || source.source || source.sourceSystem || source.mode || "",
    confidence: candidate.confidence ?? source.confidence ?? "",
    dataMode: candidate.dataMode || source.dataMode || source.mode || "",
    reason: source.reason || source.message || source.summary || "",
    requiresOperatorConfirmation:
      source.requiresOperatorConfirmation ?? source.operatorConfirmationRequired ?? source.requiresConfirmation ?? source.confirmationRequired,
  };
}

function repairSource(run, output, report) {
  return firstObject(
    run?.repairMetadata,
    run?.reportRepair,
    run?.groundingRepair,
    output.repairMetadata,
    output.reportRepair,
    output.groundingRepair,
    report?.repairMetadata,
    report?.reportRepair,
    report?.groundingRepair,
  );
}

function normalizeRepair(source) {
  if (!source) return null;
  return {
    status: source.status || source.state || source.decision || "",
    tone: statusTone(source.status || source.state || source.decision),
    attemptCount: source.attemptCount ?? source.repairAttemptCount ?? source.attempts?.length ?? "",
    stopReason: source.stopReason || source.reason || source.message || "",
  };
}

function normalizeReview(reviewGate) {
  if (!reviewGate) return null;
  const status = reviewGate.status || reviewGate.decision || "review_required";
  return {
    status,
    tone: reviewToneFromStatus(status),
    attemptCount: reviewGate.attemptCount ?? reviewGate.revisionCount ?? "",
    stopReason: reviewGate.stopReason || reviewGate.message || "",
    requiresHumanReview: reviewGate.requiresHumanReview !== false,
  };
}

function statusTone(status) {
  const normalized = String(status || "").toLowerCase();
  if (normalized.includes("fail") || normalized.includes("block") || normalized.includes("denied")) return "blocked";
  if (normalized.includes("complete") || normalized.includes("pass") || normalized.includes("stored") || normalized.includes("loaded")) return "passed";
  if (normalized.includes("running") || normalized.includes("live")) return "real";
  return "warning";
}

function hasContractPayload(output, entryResponse) {
  return Boolean(
    firstObject(output.progress, output.progressState, output.runProgress, entryResponse?.progress, entryResponse?.progressState) ||
      firstObject(output.locationGate, output.locationConfirmationGate, output.locationConfirmation) ||
      firstObject(output.repairMetadata, output.reportRepair, output.groundingRepair) ||
      output.reportStatus,
  );
}

function isConfirmationText(value) {
  const normalized = String(value || "").trim().toLowerCase();
  return (
    ["yes", "yes please", "confirm", "confirmed", "launch", "go", "go ahead", "confirm and launch"].includes(normalized) ||
    normalized.includes("please launch")
  );
}

function buildCloudEntryPayload({ submittedText, request, uploads, pendingEntry }) {
  const isConfirmationTurn = pendingEntry?.status === "confirmation_required" && pendingEntry?.intake;
  const shouldConfirm = isConfirmationTurn && isConfirmationText(submittedText);
  const reportSessionId = frontendReportSessionId();
  const payload = {
    entryTurn: true,
    caller: "frontend",
    conversationId: reportSessionId,
    entryAgentId: "fieldbrief-demo-ui",
    confirmedByUser: Boolean(shouldConfirm),
    message: submittedText,
    materials: uploads.map((upload) => ({
      materialId: upload.materialId || upload.id,
      sourceSystem: upload.sourceSystem || "fieldbrief-dev",
      type: upload.type,
      label: upload.label,
      summary: upload.summary,
      sizeBytes: upload.sizeBytes,
      access: upload.access || { mode: "fieldbrief_mock_reference" },
    })),
    runtimeOptions: {
      fixturePack: request.fixturePack,
      useBedrock: request.useBedrock,
      includePlanningFixture: request.includePlanningFixture,
      simulateMapFailure: request.simulateMapFailure,
    },
    reportAccess: {
      schemaVersion: REPORT_ACCESS_SCHEMA_VERSION,
      mode: "asi_session",
      sessionId: reportSessionId,
    },
  };
  if (shouldConfirm) {
    payload.intake = pendingEntry.intake;
  }
  return payload;
}

function buildLocalAsiOnePayload({ submittedText, request, uploads }) {
  const reportSessionId = frontendReportSessionId();
  return {
    localAsiOne: true,
    sessionId: reportSessionId,
    conversationId: reportSessionId,
    message: submittedText,
    confirmedByUser: true,
    runtimeOptions: {
      ...request,
      materials: uploads.map((upload) => ({
        materialId: upload.materialId || upload.id,
        sourceSystem: upload.sourceSystem || "fieldbrief-dev",
        type: upload.type,
        label: upload.label,
        summary: upload.summary,
        sizeBytes: upload.sizeBytes,
        access: upload.access || { mode: "fieldbrief_mock_reference" },
      })),
    },
  };
}

function caseIdFromPath() {
  const match = window.location.pathname.match(/^\/case\/([^/]+)\/?$/);
  return match ? decodeURIComponent(match[1]) : "";
}

function buildReportLookupPayload(caseId) {
  const reportSessionId = frontendReportSessionId();
  if (USE_LOCAL_ASIONE) {
    return {
      input: {
        operation: "getReport",
        caseId,
        reportAccess: {
          schemaVersion: REPORT_ACCESS_SCHEMA_VERSION,
          mode: "dev_local",
          caseId,
          sessionId: reportSessionId,
          authorizedCaseIds: [caseId],
        },
      },
    };
  }
  return {
    frontendInvoke: true,
    operation: "getReport",
    caseId,
    conversationId: reportSessionId,
    entryAgentId: "fieldbrief-demo-ui",
    reportAccess: {
      schemaVersion: REPORT_ACCESS_SCHEMA_VERSION,
      mode: "asi_session",
      caseId,
      sessionId: reportSessionId,
      authorizedCaseIds: [caseId],
    },
  };
}

function frontendReportSessionId() {
  if (typeof window === "undefined") return "frontend-demo-session";
  const urlSession = new URLSearchParams(window.location.search).get("reportSessionId");
  if (urlSession) {
    window.sessionStorage.setItem(REPORT_SESSION_STORAGE_KEY, urlSession);
    return urlSession;
  }
  const existing = window.sessionStorage.getItem(REPORT_SESSION_STORAGE_KEY);
  if (existing) return existing;
  const generated =
    window.crypto?.randomUUID?.() ||
    `frontend-demo-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
  window.sessionStorage.setItem(REPORT_SESSION_STORAGE_KEY, generated);
  return generated;
}

function SceneViewer({ scene, annotations, location, sceneMode }) {
  const containerRef = useRef(null);
  const markerItems = useMemo(
    () =>
      toList(annotations).map((annotation, index) => ({
        annotation,
        marker: String(index + 1),
        title: annotation.title || annotation.label || annotation.id || `Marker ${index + 1}`,
        status: annotation.confidence || annotation.status || annotation.source_type || "review",
      })),
    [annotations],
  );

  useEffect(() => {
    if (!containerRef.current || !scene?.center) return undefined;

    Cesium.Ion.defaultAccessToken = "";
    const viewer = new Cesium.Viewer(containerRef.current, {
      animation: false,
      timeline: false,
      baseLayer: false,
      geocoder: false,
      homeButton: false,
      sceneModePicker: false,
      baseLayerPicker: false,
      navigationHelpButton: false,
      fullscreenButton: false,
      infoBox: false,
      selectionIndicator: false,
    });

    viewer.scene.globe.baseColor = Cesium.Color.fromCssColorString("#e6ece9");
    viewer.scene.skyAtmosphere.show = false;
    viewer.scene.fog.enabled = false;

    const center = scene.center;
    viewer.entities.add({
      name: "Review area",
      polygon: {
        hierarchy: Cesium.Cartesian3.fromDegreesArray([
          center.longitude - 0.006,
          center.latitude - 0.004,
          center.longitude + 0.006,
          center.latitude - 0.004,
          center.longitude + 0.006,
          center.latitude + 0.004,
          center.longitude - 0.006,
          center.latitude + 0.004,
        ]),
        height: 0,
        material: Cesium.Color.fromCssColorString("#7fb9a7").withAlpha(0.36),
        outline: true,
        outlineColor: Cesium.Color.fromCssColorString("#0b6f65"),
      },
    });

    markerItems.forEach(({ annotation, marker, title }) => {
      viewer.entities.add({
        name: title,
        position: Cesium.Cartesian3.fromDegrees(annotation.longitude, annotation.latitude, 24),
        point: {
          pixelSize: annotation.confidence === "low" ? 12 : 10,
          color: Cesium.Color.fromCssColorString(annotation.confidence === "low" ? "#d97706" : "#1d4ed8"),
          outlineColor: Cesium.Color.WHITE,
          outlineWidth: 2,
        },
        label: {
          text: marker,
          font: "700 13px sans-serif",
          fillColor: Cesium.Color.fromCssColorString("#111827"),
          showBackground: true,
          backgroundColor: Cesium.Color.WHITE.withAlpha(0.9),
          pixelOffset: new Cesium.Cartesian2(0, -20),
        },
      });
    });

    const cameraRange = Number(scene.camera?.rangeMeters) || 1500;
    viewer.camera.flyTo({
      destination: Cesium.Cartesian3.fromDegrees(center.longitude, center.latitude, cameraRange),
      orientation: {
        heading: Cesium.Math.toRadians(scene.camera?.headingDegrees || 0),
        pitch: Cesium.Math.toRadians(scene.camera?.pitchDegrees || -48),
      },
      duration: 0,
    });

    return () => {
      if (!viewer.isDestroyed()) viewer.destroy();
    };
  }, [scene, markerItems]);

  if (!scene) {
    return (
      <div className="empty-map">
        <MapPinned size={24} />
        <span>{sceneMode?.label || "Scene not run"}: map appears after the site is resolved.</span>
        <em className={`status ${sceneMode?.tone || "warning"}`}>{sceneMode?.label || "Scene not run"}</em>
        <SceneContextBadges sceneMode={sceneMode} />
      </div>
    );
  }

  return (
    <div className="scene-shell">
      <div ref={containerRef} className="scene-viewer" />
      <div className="map-caption">
        <strong>{location?.label || "Selected site"}</strong>
        <span>{markerItems.length} mapped risk marker(s)</span>
        {markerItems.length > 0 && (
          <ol className="marker-key" aria-label="3D marker key">
            {markerItems.map(({ annotation, marker, title, status }) => (
              <li key={annotation.id || `${marker}-${title}`}>
                <span>{marker}</span>
                <strong>{title}</strong>
                <em className={`status ${status}`}>{status}</em>
              </li>
            ))}
          </ol>
        )}
        <em className={`status ${sceneMode?.tone || "warning"}`}>{sceneMode?.label || "Unknown data mode"}</em>
        <SceneContextBadges sceneMode={sceneMode} />
      </div>
    </div>
  );
}

function SceneContextBadges({ sceneMode }) {
  const badges = toList(sceneMode?.badges);
  if (!badges.length) return null;
  return (
    <div className="scene-context">
      <div className="scene-badges" aria-label="Scene source and data mode">
        {badges.slice(0, 6).map((badge) => (
          <span className={`source-badge ${badge.tone || "warning"}`} key={`${badge.label}-${badge.value}`}>
            <strong>{badge.label}</strong>
            <em>{badge.value}</em>
          </span>
        ))}
      </div>
      {sceneMode.summary && <small>{sceneMode.summary}</small>}
    </div>
  );
}

function RiskCards({ hazards, briefing, notice }) {
  const items = toList(hazards).slice(0, 6);
  return (
    <section className="panel">
      <div className="panel-heading">
        <AlertTriangle size={18} />
        <h2>Risk Review</h2>
      </div>
      <div className="risk-grid">
        {items.length ? (
          items.map((hazard, index) => (
            <article key={hazard.id || hazard.title || hazard.type || `risk-${index}`}>
              <strong>{riskCardTitle(hazard, index)}</strong>
              <em className={`status ${riskCardStatus(hazard)}`}>{riskCardStatus(hazard)}</em>
              <p>{riskCardBody(hazard)}</p>
              {riskCardReferences(hazard) && <small>{riskCardReferences(hazard)}</small>}
            </article>
          ))
        ) : (
          <p className="empty-copy">{notice || "Risk cards appear after the agent runs tools."}</p>
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

function riskCardTitle(item, index) {
  const title = item.title || item.label || item.name;
  if (title && title !== "unknown-finding") return title;
  const typedTitle = humanizeToken(item.type || item.category);
  if (typedTitle && typedTitle !== "Unspecified") return typedTitle;
  const idTitle = humanizeToken(item.id);
  if (idTitle && idTitle !== "Unknown Finding") return idTitle;
  return `Candidate finding ${index + 1}`;
}

function riskCardStatus(item) {
  return item.confidence || item.severity || item.level || item.type || item.category || "review";
}

function riskCardBody(item) {
  return (
    item.reason ||
    item.summary ||
    item.note ||
    item.description ||
    item.rationale ||
    item.evidence ||
    "Review this item before the site visit."
  );
}

function riskCardReferences(item) {
  const refs = riskReferenceIds(item);
  const parts = [];
  if (refs.sourceIds.length) parts.push(`Sources: ${refs.sourceIds.join(", ")}`);
  if (refs.evidenceIds.length) parts.push(`Evidence: ${refs.evidenceIds.join(", ")}`);
  return parts.join(" · ");
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
          <strong>{runtime?.activeAgentMode || runtime?.entryAgentMode || "not run"}</strong>
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
          {toList(evidence).map((item) => (
            <article className="compact-row" key={item.id}>
              <strong>{item.title}</strong>
              <span>{item.source}</span>
              <small>{item.status}</small>
            </article>
          ))}
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

function ReviewAndDataQuality({ report }) {
  const reviewGate = report?.reviewGate || {};
  const dataQuality = report?.dataQuality || {};
  const openWeb = report?.externalSignals?.openWeb || {};
  const reviewState = reviewStateFromReport(report);
  const missingItems = Object.entries(dataQuality.completeness || {})
    .filter(([, present]) => !present)
    .map(([key]) => humanizeCompleteness(key));
  const notes = listText(reviewGate.reviewerNotes);
  const caveats = [
    ...listText(reviewGate.caveats),
    ...listText(reviewGate.issues),
    ...listText(reviewGate.requiredRevisions),
  ];
  const gaps = listText(dataQuality.gaps);
  const warnings = listText(dataQuality.warnings);

  return (
    <section className="panel assurance-panel">
      <div className="panel-heading">
        <ShieldCheck size={18} />
        <h2>Review + Data Quality</h2>
      </div>
      <div className="review-summary">
        <article>
          <span>Review gate</span>
          <strong>{reviewState.label}</strong>
          <em className={`status ${reviewState.tone}`}>{reviewState.label}</em>
          <p>{reviewGate.message || "Review status appears after the supervisor returns a structured report."}</p>
        </article>
        <article>
          <span>Safety boundary</span>
          <strong>{reviewGate.requiresHumanReview === false ? "Human review not flagged" : "Human review required"}</strong>
          <p>Non-certified pre-visit review pack. Not RAMS certification, emergency guidance, or approval to work.</p>
        </article>
        <article>
          <span>Open-web signals</span>
          <strong>{humanizeToken(openWeb.status || "not_configured")}</strong>
          <p>{toList(openWeb.items).length ? `${toList(openWeb.items).length} signal(s) included as context.` : "No open-web signals are included."}</p>
        </article>
      </div>
      <div className="assurance-grid">
        <div>
          <h3>Report Sections</h3>
          {toList(report?.sections).map((section) => (
            <article className="compact-row section-row" key={section.id || section.title}>
              <strong>{section.title || humanizeToken(section.id)}</strong>
              <span>{firstText(toList(section.body)[0])}</span>
              <small className={`status ${section.status || "review_required"}`}>{humanizeToken(section.status || "review_required")}</small>
            </article>
          ))}
        </div>
        <div>
          <h3>Limitations</h3>
          <article className="compact-row">
            <strong>{dataQuality.dataMode || "unknown data mode"}</strong>
            <span>{missingItems.length ? `Missing: ${missingItems.join(", ")}` : "Completeness flags are satisfied."}</span>
          </article>
          {[...caveats, ...notes, ...gaps, ...warnings].slice(0, 8).map((item) => (
            <article className="compact-row" key={item}>
              <span>{item}</span>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

function WorkflowStatusPanel({ contracts }) {
  const { entryRouting, progress, locationGate, repair, review, sceneMode } = contracts;
  return (
    <section className="panel contract-panel">
      <div className="panel-heading">
        <Radar size={18} />
        <h2>Progress + Gate State</h2>
      </div>
      <div className="contract-grid">
        <article>
          <span>Entry routing</span>
          {entryRouting ? (
            <>
              <strong>{humanizeToken(entryRouting.route || entryRouting.status || "entry")}</strong>
              <em className={`status ${entryRouting.tone}`}>{humanizeToken(entryRouting.status || "available")}</em>
              <MetaRow label="Agent mode" value={entryRouting.activeAgentMode && humanizeToken(entryRouting.activeAgentMode)} />
              <MetaRow label="Tools" value={entryRouting.toolsStarted} />
              <MetaRow label="No-tool reason" value={entryRouting.noToolReason && humanizeToken(entryRouting.noToolReason)} />
            </>
          ) : (
            <p>Entry routing metadata not returned yet.</p>
          )}
        </article>
        <article>
          <span>Run progress</span>
          {progress ? (
            <>
              <strong>{humanizeToken(progress.status)}</strong>
              <em className={`status ${progress.tone}`}>{humanizeToken(progress.status)}</em>
              <p>{progress.currentStep || "Current step not returned yet."}</p>
              {progress.summary && <small>{progress.summary}</small>}
              <MetaRow label="Model calls" value={progress.modelCallCount} />
              <MetaRow label="Updated" value={progress.updatedAt} />
              <MetaRow label="Fallback" value={progress.fallbackReason} />
            </>
          ) : (
            <p>Progress contract not returned yet.</p>
          )}
        </article>
        <article>
          <span>Location confirmation</span>
          {locationGate ? (
            <>
              <strong>{locationGate.candidateLabel || "Candidate not named"}</strong>
              <em className={`status ${locationGate.tone}`}>{humanizeToken(locationGate.status)}</em>
              <MetaRow label="Source" value={locationGate.source} />
              <MetaRow label="Confidence" value={locationGate.confidence} />
              <MetaRow label="Data mode" value={locationGate.dataMode} />
              <MetaRow
                label="Operator confirmation"
                value={present(locationGate.requiresOperatorConfirmation) ? (locationGate.requiresOperatorConfirmation ? "Required" : "Not required") : ""}
              />
              {locationGate.reason && <small>{locationGate.reason}</small>}
            </>
          ) : (
            <p>Location gate fields not returned yet.</p>
          )}
        </article>
        <article>
          <span>Repair + review</span>
          {repair || review ? (
            <>
              <strong>{humanizeToken(repair?.status || review?.status || "review_required")}</strong>
              <em className={`status ${repair?.tone || review?.tone || "warning"}`}>
                {repair ? "Repair" : "Review"}
              </em>
              <MetaRow label="Repair attempts" value={repair?.attemptCount} />
              <MetaRow label="Repair stop" value={repair?.stopReason} />
              <MetaRow label="Review status" value={review?.status && humanizeToken(review.status)} />
              <MetaRow label="Review attempts" value={review?.attemptCount} />
              <small>Human-review-only output; not certification, emergency guidance, or approval to work.</small>
            </>
          ) : (
            <p>Repair and review metadata not returned yet.</p>
          )}
        </article>
        <article>
          <span>Scene data mode</span>
          <strong>{sceneMode.label}</strong>
          <em className={`status ${sceneMode.tone}`}>{sceneMode.value}</em>
          <MetaRow label="Sources" value={sceneMode.sourceIds?.length ? `${sceneMode.sourceIds.length} source(s)` : ""} />
          <MetaRow label="Features" value={present(sceneMode.featureCount) ? `${sceneMode.featureCount} mapped feature(s)` : ""} />
          <MetaRow label="Provider" value={sceneMode.provider} />
          <MetaRow label="Location source" value={sceneMode.locationSource} />
          <MetaRow label="Planning" value={sceneMode.planningStatus && humanizeToken(sceneMode.planningStatus)} />
          <MetaRow label="Fallback" value={sceneMode.fallbackReason} />
          <small>Review context only; source badges do not make public data authoritative site evidence.</small>
        </article>
      </div>
    </section>
  );
}

function MetaRow({ label, value }) {
  if (!present(value)) return null;
  return (
    <dl className="meta-row">
      <dt>{label}</dt>
      <dd>{String(value)}</dd>
    </dl>
  );
}

function reviewStateFromReport(report) {
  const reviewGate = report?.reviewGate || {};
  const raw = String(reviewGate.decision || reviewGate.status || report?.status || "review_required").toLowerCase();
  if (["pass", "passed", "review_passed"].includes(raw)) return { label: "Passed", tone: "passed" };
  if (["pass_with_caveats", "passed_with_caveats"].includes(raw)) return { label: "Passed with caveats", tone: "caveats" };
  if (["block", "blocked"].includes(raw)) return { label: "Blocked", tone: "blocked" };
  return { label: "Review required", tone: "review_required" };
}

function humanizeCompleteness(key) {
  return humanizeToken(String(key).replace(/^has/, "").replace(/([a-z])([A-Z])/g, "$1 $2"));
}

function App() {
  const [request, setRequest] = useState(DEFAULT_REQUEST);
  const [prompt, setPrompt] = useState(STARTER_PROMPT);
  const [entryResponse, setEntryResponse] = useState(null);
  const [agentOpen, setAgentOpen] = useState(false);
  const [messages, setMessages] = useState([
    {
      id: "welcome",
      role: "assistant",
      text: "Dev/debug ASI simulation only. ASI:ONE is the real user entry; use this panel to test intake, confirmation, and report handoff behavior.",
    },
  ]);
  const [uploads, setUploads] = useState([]);
  const [run, setRun] = useState(null);
  const [caseId, setCaseId] = useState(caseIdFromPath());
  const [persistence, setPersistence] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const composerRef = useRef(null);

  const ui = entryResponse?.uiState || runToUiState(run, entryResponse);
  const runtime = entryResponse?.runtime || run?.runtime || {};
  const contracts = contractStateFrom({ run, entryResponse, persistence });
  const reviewGate = reviewGateFromRun(run);
  const reviewStatus = reviewGate?.status || reviewGate?.decision || "";
  const reviewTone = reviewToneFromStatus(reviewStatus);
  const safetyTone = ui.safety?.allowed === false ? "blocked" : ui.safety?.level === "needs_input" ? "warning" : "allowed";
  const pendingConfirmation = entryResponse?.status === "confirmation_required" && entryResponse?.intake;

  async function sendToFieldBrief(nextPrompt = prompt, appendMessage = true) {
    const submittedText = nextPrompt.trim();
    if (!submittedText || loading) return;
    if (appendMessage) {
      setMessages((current) => [
        ...current,
        {
          id: `user-${Date.now()}`,
          role: "user",
          text: submittedText,
        },
      ]);
      setPrompt("");
    }
    setLoading(true);
    setError("");
    try {
      if (!ENTRY_AGENT_URL) {
        throw new Error("Cloud entry proxy is not configured. Set VITE_CLOUD_ENTRY_PROXY_URL, or set VITE_USE_LOCAL_ASIONE=true for explicit local testing.");
      }
      const requestPayload = USE_LOCAL_ASIONE
        ? buildLocalAsiOnePayload({ submittedText, request, uploads })
        : buildCloudEntryPayload({ submittedText, request, uploads, pendingEntry: entryResponse });
      const response = await fetch(ENTRY_AGENT_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(requestPayload),
      });
      if (!response.ok) throw new Error(`Agent run failed (${response.status})`);
      const payload = await response.json();
      const output = payload.output || {};
      const nextEntryResponse = payload.output?.localAsiOne || payload.output?.entryAgent || null;
      setEntryResponse(nextEntryResponse);
      setPersistence(output.persistence || nextEntryResponse?.agentcoreOutput?.persistence || null);
      if (nextEntryResponse) {
        setMessages((current) => [
          ...current,
          {
            id: nextEntryResponse.runId || `assistant-${Date.now()}`,
            role: "assistant",
            text: nextEntryResponse.assistantMessage || payload.output?.delivery?.customerSummary?.headline || "Supervisor workflow completed.",
            questions: nextEntryResponse.clarifyingQuestions || [],
            confirmationSummary: nextEntryResponse.confirmation?.summary || "",
            activityPrompts: nextEntryResponse.activityPrompts || null,
          },
        ]);
      }
      if (["clarification_required", "confirmation_required"].includes(nextEntryResponse?.status)) {
        setAgentOpen(true);
        setRun(null);
        return;
      }
      const nextRun = attachStructuredReport(
        nextEntryResponse?.run || payload.output?.run,
        output.structuredReport,
        output.reviewMetadata || output.reviewGate,
        output,
        nextEntryResponse || {},
      );
      if (!nextRun && !hasContractPayload(output, nextEntryResponse)) {
        throw new Error("Entry agent response did not include a supervisor run or progress contract");
      }
      const nextCaseId = output.caseId || nextEntryResponse?.caseId || nextRun?.caseId || "";
      setCaseId(nextCaseId);
      if (nextCaseId && output.persistence?.status === "stored") {
        window.history.replaceState(null, "", `/case/${encodeURIComponent(nextCaseId)}`);
      }
      setRun(nextRun);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function loadCaseReport(nextCaseId) {
    if (!nextCaseId || loading) return;
    setLoading(true);
    setError("");
    try {
      if (!REPORT_LOOKUP_URL) {
        throw new Error("Report lookup is not configured. Set VITE_CLOUD_ENTRY_PROXY_URL, or use local ASI:ONE mode with the AgentCore proxy.");
      }
      const response = await fetch(REPORT_LOOKUP_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(buildReportLookupPayload(nextCaseId)),
      });
      if (!response.ok) throw new Error(`Report lookup failed (${response.status})`);
      const payload = await response.json();
      const output = payload.output || {};
      setPersistence(output.persistence || null);
      if (!output.run && !hasContractPayload(output, null)) {
        throw new Error(`No stored report found for ${nextCaseId}.`);
      }
      setEntryResponse(null);
      setCaseId(output.caseId || nextCaseId);
      const nextRun = attachStructuredReport(output.run, output.structuredReport, output.reviewMetadata || output.reviewGate, output);
      setRun(nextRun);
      if (!nextRun) {
        setEntryResponse({
          status: output.progress?.status || output.progressState?.status || output.reportStatus || "report_lookup",
          assistantMessage: output.progress?.summary || output.progressState?.summary || "Report lookup returned status metadata.",
          agentcoreOutput: output,
        });
      }
      setMessages([
        {
          id: `case-${nextCaseId}`,
          role: "assistant",
          text: output.structuredReport?.executiveSummary?.headline || "Stored report loaded.",
        },
      ]);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  function sendMessage(event) {
    event.preventDefault();
    sendToFieldBrief(prompt, true);
  }

  function revisePendingIntake() {
    setEntryResponse(null);
    setPrompt("");
    composerRef.current?.focus();
  }

  function registerMockUpload() {
    setUploads((current) => [
      ...current,
      {
        id: `local-upload-${current.length + 1}`,
        materialId: `fieldbrief_mock_material_${current.length + 1}`,
        sourceSystem: "fieldbrief-dev",
        type: "application/pdf",
        label: `Test evidence ${current.length + 1}`,
        summary: "Local dev material-reference metadata registered by the FieldBrief ASI simulation.",
        sizeBytes: 1024,
        access: { mode: "fieldbrief_mock_reference" },
      },
    ]);
  }

  function resetDemo() {
    setRequest(DEFAULT_REQUEST);
    setPrompt(STARTER_PROMPT);
    setMessages([
      {
        id: "welcome",
        role: "assistant",
        text: "Dev/debug ASI simulation only. ASI:ONE is the real user entry; use this panel to test intake, confirmation, and report handoff behavior.",
      },
    ]);
    setUploads([]);
    setRun(null);
    setEntryResponse(null);
    setCaseId("");
    setPersistence(null);
    if (window.location.pathname.startsWith("/case/")) {
      window.history.replaceState(null, "", "/");
    }
  }

  useEffect(() => {
    const routeCaseId = caseIdFromPath();
    if (routeCaseId) {
      loadCaseReport(routeCaseId);
    }
  }, []);

  return (
    <main className="app-shell product-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">3D-RAMS AgentCore Workflow</p>
          <h1>3D-RAMS Report Console</h1>
          <p className="topbar-summary">
            Report and debug surface for ASI:ONE-led workflows. Open FieldBrief only as an Evan/dev ASI simulation; root page load does not start an entry run.
          </p>
        </div>
        <div className="status-stack">
          <button className="secondary" onClick={() => setAgentOpen(true)}>
            <MessageSquare size={16} />
            {FIELD_BRIEF_LABEL}
          </button>
          <button className="icon-button" aria-label="Reset request" onClick={resetDemo}>
            <RotateCcw size={16} />
          </button>
          <div className={`safety-pill ${safetyTone}`}>
            <ShieldCheck size={16} />
            {ui.safety?.level || "ready"}
          </div>
          {reviewStatus && (
            <div className={`safety-pill ${reviewTone}`} title={reviewGate?.message || "review status"}>
              <ShieldCheck size={16} />
              Review {humanizeToken(reviewStatus)}
            </div>
          )}
          <div className="safety-pill pending">
            <Cloud size={16} />
            {runtime.subagentExecutionMode || runtime.supervisorRuntime || (USE_LOCAL_ASIONE ? "local" : "cloud")}
          </div>
          <div className={`safety-pill ${request.useBedrock ? "warning" : "allowed"}`}>
            <GitBranch size={16} />
            Live model {request.useBedrock ? "on" : "off"}
          </div>
          {caseId && (
            <div className="safety-pill pending" title={persistence?.status || "case id"}>
              {caseId}
            </div>
          )}
        </div>
      </header>

      {agentOpen && (
        <div className="agent-modal-backdrop" role="presentation">
          <section className="agent-modal agent-chat panel" role="dialog" aria-modal="true" aria-labelledby="fieldbrief-title">
            <div className="panel-heading agent-chat-heading">
              <Bot size={18} />
              <h2 id="fieldbrief-title">{FIELD_BRIEF_LABEL}</h2>
              <button className="icon-button" aria-label={`Collapse ${FIELD_BRIEF_LABEL}`} onClick={() => setAgentOpen(false)}>
                <X size={16} />
              </button>
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
                  {message.confirmationSummary && <p className="confirmation-summary">{message.confirmationSummary}</p>}
                  {message.activityPrompts?.items?.length > 0 && (
                    <div className="confirmation-summary">
                      <p>{message.activityPrompts.notice || "Generic considerations from your wording, not site evidence."}</p>
                      <ul>
                        {message.activityPrompts.items.map((item) => (
                          <li key={item.family || item.label}>
                            <strong>{item.label || item.family}</strong>
                            {Array.isArray(item.considerations) && item.considerations.length > 0 && (
                              <ul>
                                {item.considerations.map((consideration) => (
                                  <li key={consideration}>{consideration}</li>
                                ))}
                              </ul>
                            )}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </article>
              ))}
            </div>
            {pendingConfirmation && (
              <div className="confirmation-actions" aria-label="Pending confirmation">
                <button type="button" onClick={() => sendToFieldBrief("Confirm and launch", true)} disabled={loading}>
                  <ShieldCheck size={16} />
                  Confirm launch
                </button>
                <button className="secondary" type="button" onClick={revisePendingIntake} disabled={loading}>
                  <RotateCcw size={16} />
                  Revise details
                </button>
              </div>
            )}
            <div className="upload-strip">
              <button className="secondary" type="button" onClick={registerMockUpload}>
                <FileUp size={16} />
                Register test material ref
              </button>
              <label className="toggle-control">
                <input
                  type="checkbox"
                  checked={request.useBedrock}
                  onChange={(event) => setRequest((current) => ({ ...current, useBedrock: event.target.checked }))}
                />
                <span>Use live model</span>
              </label>
              <span>{uploads.length ? `${uploads.length} material reference(s) registered` : "Dev metadata only; ASI:ONE owns real material ingestion."}</span>
            </div>
            <form className="composer" onSubmit={sendMessage}>
              <textarea ref={composerRef} value={prompt} onChange={(event) => setPrompt(event.target.value)} />
              <button disabled={loading || !prompt.trim()}>
                <Send size={16} />
                {loading ? "Running" : "Send"}
              </button>
            </form>
          </section>
        </div>
      )}

      {error && <div className="error-banner">{error}</div>}

      <section className="product-grid report-only">
        <section className="panel map-panel">
          <div className="panel-heading">
            <MapPinned size={18} />
            <h2>3D Site Risk Scene</h2>
          </div>
          <SceneViewer scene={ui.scene} annotations={ui.annotations} location={ui.location} sceneMode={contracts.sceneMode} />
        </section>
      </section>

      <WorkflowStatusPanel contracts={contracts} />

      <section className="insight-grid">
        <RiskCards hazards={ui.hazards} briefing={ui.briefing} notice={ui.riskReviewNotice} />
        <ReviewAndDataQuality report={ui.structuredReport} />
        <EvidenceAndTrace evidence={ui.evidence} trace={ui.trace} safety={ui.safety} runtime={runtime} />
      </section>
    </main>
  );
}

export default App;
