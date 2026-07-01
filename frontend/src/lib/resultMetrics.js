import { RESEARCH_DOMAINS, RESEARCH_DOMAIN_IDS } from "../data/researchDomains";
import {
  getBriefing,
  getEvidence,
  getHazards,
  getSafety,
  getTrace,
  toList,
} from "./uiState";

const DOMAIN_KEYWORDS = {
  [RESEARCH_DOMAIN_IDS.WEATHER]: ["weather", "rain", "wind", "storm", "metar", "atmospheric"],
  [RESEARCH_DOMAIN_IDS.TERRAIN]: ["terrain", "slope", "ground", "topography", "height", "embankment"],
  [RESEARCH_DOMAIN_IDS.ACCESS]: ["access", "route", "road", "vehicle", "pedestrian", "stopping", "approach"],
  [RESEARCH_DOMAIN_IDS.INFRASTRUCTURE]: ["infrastructure", "rail", "bridge", "road", "structure", "corridor"],
  [RESEARCH_DOMAIN_IDS.ENERGY_UTILITIES]: ["energy", "utility", "utilities", "ohl", "overhead", "line", "cable", "power", "service"],
  [RESEARCH_DOMAIN_IDS.WATER_FLOODING]: ["water", "flood", "river", "drainage", "thames", "watercourse"],
  [RESEARCH_DOMAIN_IDS.PLANNING_CONTEXT]: ["planning", "context", "permit", "heritage", "public", "surrounding"],
  [RESEARCH_DOMAIN_IDS.SITE_HAZARDS]: ["hazard", "risk", "constraint", "exposure", "interface"],
};

function textBlob(items) {
  return toList(items)
    .map((item) => JSON.stringify(item || {}))
    .join(" ")
    .toLowerCase();
}

function hasKeyword(blob, domainId) {
  return toList(DOMAIN_KEYWORDS[domainId]).some((keyword) => blob.includes(keyword));
}

function hasFallback(items) {
  return toList(items).some((item) => {
    const text = JSON.stringify(item || {}).toLowerCase();
    return item?.status === "fallback" || item?.fallbackReason || text.includes("fallback");
  });
}

function hasLowConfidence(items) {
  return toList(items).some((item) => {
    const text = JSON.stringify(item || {}).toLowerCase();
    return item?.confidence === "low" || text.includes("low confidence");
  });
}

function domainStatus({ domain, blob, hazards, evidence, trace, briefing, safety }) {
  if (domain.id === RESEARCH_DOMAIN_IDS.SAFETY_GATE) {
    if (safety.allowed === false) {
      return {
        status: "blocked",
        summary: safety.message || "Safety gate blocked the requested output.",
        confidenceLabel: "Blocked",
      };
    }
    return {
      status: safety.level === "ready" ? "missing" : "ready",
      summary: safety.message || "Human review required before dispatch or work planning.",
      confidenceLabel: safety.requiresHumanReview ? "Human review" : "Review",
    };
  }

  if (domain.id === RESEARCH_DOMAIN_IDS.EVIDENCE_QUALITY) {
    if (!evidence.length) {
      return {
        status: "missing",
        summary: "No evidence register has been returned yet.",
        confidenceLabel: "No evidence",
      };
    }
    if (hasFallback(evidence) || hasFallback(trace)) {
      return {
        status: "fallback",
        summary: "Some evidence or tool outputs are cached, mocked, or fallback data.",
        confidenceLabel: "Fallback visible",
      };
    }
    if (hasLowConfidence(evidence) || hasLowConfidence(hazards)) {
      return {
        status: "partial",
        summary: "Evidence is present, with low-confidence items requiring field verification.",
        confidenceLabel: "Mixed confidence",
      };
    }
    return {
      status: "ready",
      summary: `${evidence.length} evidence item(s) available for human review.`,
      confidenceLabel: "Evidence present",
    };
  }

  if (domain.id === RESEARCH_DOMAIN_IDS.SITE_HAZARDS) {
    if (!hazards.length) {
      return {
        status: "missing",
        summary: domain.fallbackSummary,
        confidenceLabel: "No hazards yet",
      };
    }
    if (hasLowConfidence(hazards)) {
      return {
        status: "partial",
        summary: `${hazards.length} candidate hazard(s), including low-confidence items.`,
        confidenceLabel: "Field check",
      };
    }
    return {
      status: "ready",
      summary: `${hazards.length} candidate hazard(s) returned for review.`,
      confidenceLabel: "Review pack",
    };
  }

  const hasDomainEvidence = hasKeyword(blob, domain.id);
  const domainFallback = hasFallback(trace) && hasKeyword(textBlob(trace), domain.id);
  const lowConfidence = hasLowConfidence(hazards) && hasKeyword(textBlob(hazards), domain.id);
  const briefingMentionsDomain = hasKeyword(textBlob([briefing]), domain.id);

  if (domainFallback) {
    return {
      status: "fallback",
      summary: `${domain.label} appears in fallback or cached tool output.`,
      confidenceLabel: "Fallback",
    };
  }
  if (hasDomainEvidence && lowConfidence) {
    return {
      status: "partial",
      summary: `${domain.label} is flagged, but includes low-confidence information.`,
      confidenceLabel: "Field check",
    };
  }
  if (hasDomainEvidence) {
    return {
      status: "ready",
      summary: `${domain.label} appears in the returned hazards, evidence, or trace.`,
      confidenceLabel: "Available",
    };
  }
  if (briefingMentionsDomain) {
    return {
      status: "partial",
      summary: `${domain.label} appears in the briefing, but supporting evidence should be checked.`,
      confidenceLabel: "Briefing mention",
    };
  }
  return {
    status: "missing",
    summary: domain.fallbackSummary,
    confidenceLabel: "Not confirmed",
  };
}

export function countEvidenceItems(evidence) {
  return toList(evidence).length;
}

export function countTraceSteps(trace) {
  return toList(trace).length;
}

export function countHazards(hazards) {
  return toList(hazards).length;
}

export function countLowConfidenceItems(hazards, evidence, trace) {
  return [...toList(hazards), ...toList(evidence), ...toList(trace)].filter((item) =>
    hasLowConfidence([item]),
  ).length;
}

export function countFallbackItems(evidence, trace) {
  return [...toList(evidence), ...toList(trace)].filter((item) => hasFallback([item])).length;
}

export function estimateResearchCoverage(uiState) {
  const hazards = getHazards(uiState);
  const evidence = getEvidence(uiState);
  const trace = getTrace(uiState);
  const briefing = getBriefing(uiState);
  const safety = getSafety(uiState);
  const blob = textBlob([hazards, evidence, trace, briefing, safety]);

  return RESEARCH_DOMAINS.map((domain) => ({
    id: domain.id,
    label: domain.label,
    ...domainStatus({ domain, blob, hazards, evidence, trace, briefing, safety }),
  }));
}
