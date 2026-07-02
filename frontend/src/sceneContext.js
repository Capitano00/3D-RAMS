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

function uniqueText(values) {
  return [...new Set(values.map((value) => String(value || "").trim()).filter(Boolean))];
}

function firstPresent(...values) {
  return values.find(present) || "";
}

function statusTone(status) {
  const normalized = String(status || "").toLowerCase();
  if (normalized.includes("fail") || normalized.includes("fallback")) return "fallback";
  if (normalized.includes("unavailable") || normalized.includes("disabled") || normalized.includes("skipped")) return "warning";
  if (normalized.includes("cached")) return "cached";
  if (normalized.includes("live")) return "real";
  if (normalized.includes("synthetic") || normalized.includes("mock")) return "fixture";
  return "warning";
}

function modeLabel(raw, hasSceneFallback) {
  const normalized = String(raw || "").toLowerCase();
  if (hasSceneFallback) return "Fallback";
  if (normalized.includes("cached")) return "Cached fixture";
  if (normalized.includes("synthetic")) return "Synthetic fixture";
  if (normalized.includes("unavailable")) return "Unavailable";
  if (normalized.includes("disabled")) return "Disabled";
  if (normalized.includes("live") || normalized.includes("terrain")) return "Live-backed";
  return humanizeToken(raw || "not-run");
}

function firstTraceFallback(trace) {
  return toList(trace).find((step) => {
    const name = String(step?.name || step?.id || "").toLowerCase();
    const status = String(step?.status || "").toLowerCase();
    return (name.includes("geospatial") || name.includes("scene") || name.includes("planning")) && (status.includes("fallback") || step?.fallbackReason);
  });
}

function sourceIdsFrom(run, report, sourceItems, planningData, candidate) {
  return uniqueText([
    ...toList(run?.scene?.sourceIds),
    ...toList(run?.location?.sourceIds),
    ...toList(report?.site?.sourceIds),
    ...toList(planningData?.sourceIds),
    candidate?.sourceId,
    ...toList(sourceItems).map((source) => source?.id),
  ]);
}

export function sceneModeFrom(run, report, persistence, entryResponse = null) {
  const scene = firstObject(run?.scene, report?.visualization?.scene) || {};
  const location = firstObject(run?.location, report?.site) || {};
  const planningData = firstObject(run?.runtime?.planningData, report?.runtime?.planningData) || {};
  const locationConfirmation = firstObject(run?.locationConfirmation, report?.locationConfirmation) || {};
  const candidate =
    firstObject(
      locationConfirmation.candidate,
      toList(locationConfirmation.candidates)[0],
      entryResponse?.intake?.locationCandidate,
      entryResponse?.locationCandidate,
    ) || {};
  const sourceItems = [...toList(run?.sources), ...toList(report?.evidenceRegister?.sources)];
  const traceFallback = firstTraceFallback(run?.trace || report?.trace);
  const planningStatusText = String(planningData.status || "").toLowerCase();
  const fallbackReason = firstPresent(
    traceFallback?.fallbackReason,
    scene.fallbackReason,
    location.fallbackReason,
    (planningStatusText.includes("fail") || planningStatusText.includes("unavailable")) && planningData.fallbackReason,
  );
  const hasSceneFallback =
    String(traceFallback?.status || "").toLowerCase().includes("fallback") ||
    String(planningData.status || "").toLowerCase().includes("failed");
  const raw = firstPresent(
    scene.dataMode,
    location.dataMode,
    report?.dataQuality?.dataMode,
    run?.runtime?.fixturePackMode,
    report?.runtime?.fixturePackMode,
    planningData.dataMode,
    persistence?.status,
    "not-run",
  );
  const label = modeLabel(raw, hasSceneFallback);
  const sourceIds = sourceIdsFrom(run, report, sourceItems, planningData, candidate);
  const featureCount = firstPresent(scene.featureCount, planningData.featureCount);
  const provider = firstPresent(scene.provider, planningData.provider);
  const locationSource = firstPresent(candidate.source, locationConfirmation.source);
  const planningStatus = firstPresent(planningData.status, planningData.dataMode);
  const freshness = firstPresent(planningData.freshness, scene.freshness, location.freshness);
  const badges = [
    { label: "Scene", value: label, tone: hasSceneFallback ? "fallback" : statusTone(raw) },
    { label: "Data", value: raw, tone: statusTone(raw) },
    sourceIds.length ? { label: "Sources", value: `${sourceIds.length} source${sourceIds.length === 1 ? "" : "s"}`, tone: "cached" } : null,
    present(featureCount) ? { label: "Features", value: `${featureCount} feature${Number(featureCount) === 1 ? "" : "s"}`, tone: "cached" } : null,
    planningStatus ? { label: "Planning", value: humanizeToken(planningStatus), tone: statusTone(planningStatus) } : null,
    locationSource ? { label: "Location", value: locationSource, tone: statusTone(candidate.dataMode || locationConfirmation.dataMode || raw) } : null,
    freshness ? { label: "Freshness", value: freshness, tone: "cached" } : null,
    fallbackReason ? { label: "Fallback", value: fallbackReason, tone: "fallback" } : null,
  ].filter(Boolean);
  const summaryParts = [
    provider && `Provider: ${provider}`,
    sourceIds.length && `${sourceIds.length} source${sourceIds.length === 1 ? "" : "s"}`,
    present(featureCount) && `${featureCount} mapped feature${Number(featureCount) === 1 ? "" : "s"}`,
    locationSource && `Location source: ${locationSource}`,
  ].filter(Boolean);
  return {
    value: String(raw),
    label,
    tone: hasSceneFallback ? "fallback" : statusTone(raw),
    badges,
    sourceIds,
    featureCount,
    provider,
    planningStatus,
    locationSource,
    freshness,
    fallbackReason,
    summary: summaryParts.join(" · "),
  };
}
