const EMPTY_BRIEFING = {
  headline: "",
  summary: [],
  priority_checks: [],
  before_site_visit: [],
  limitations: [],
  generation_mode: "not-run",
};

const EMPTY_SAFETY = {
  allowed: true,
  level: "ready",
  message: "Human review required before dispatch or work planning.",
  triggeredRules: [],
  requiresHumanReview: true,
  decisionId: "not-run",
};

export function toList(value) {
  return Array.isArray(value) ? value : [];
}

function toObject(value) {
  return value && typeof value === "object" && !Array.isArray(value) ? value : {};
}

export function getLocation(uiState) {
  const location = toObject(toObject(uiState).location);
  return {
    label: location.label || "Unresolved site",
    latitude: Number.isFinite(location.latitude) ? location.latitude : null,
    longitude: Number.isFinite(location.longitude) ? location.longitude : null,
    ...location,
  };
}

export function getScene(uiState) {
  const scene = toObject(toObject(uiState).scene);
  return Object.keys(scene).length ? scene : null;
}

export function getAnnotations(uiState) {
  return toList(toObject(uiState).annotations);
}

export function getHazards(uiState) {
  return toList(toObject(uiState).hazards);
}

export function getEvidence(uiState) {
  return toList(toObject(uiState).evidence);
}

export function getTrace(uiState) {
  return toList(toObject(uiState).trace);
}

export function getBriefing(uiState) {
  const briefing = toObject(toObject(uiState).briefing);
  return {
    ...EMPTY_BRIEFING,
    ...briefing,
    summary: toList(briefing.summary),
    priority_checks: toList(briefing.priority_checks),
    before_site_visit: toList(briefing.before_site_visit),
    limitations: toList(briefing.limitations),
  };
}

export function getSafety(uiState) {
  const safety = toObject(toObject(uiState).safety);
  return {
    ...EMPTY_SAFETY,
    ...safety,
    triggeredRules: toList(safety.triggeredRules),
    requiresHumanReview: safety.requiresHumanReview !== false,
  };
}

export function getRuntime(run) {
  return toObject(toObject(run).runtime);
}

export function getSources(uiState) {
  const sources = toObject(uiState).sources || toObject(toObject(uiState).architecture).sources;
  return toList(sources);
}
