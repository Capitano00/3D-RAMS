export const RESEARCH_DOMAIN_IDS = {
  WEATHER: "weather",
  TERRAIN: "terrain",
  ACCESS: "access",
  INFRASTRUCTURE: "infrastructure",
  ENERGY_UTILITIES: "energy-utilities",
  WATER_FLOODING: "water-flooding",
  PLANNING_CONTEXT: "planning-context",
  SITE_HAZARDS: "site-hazards",
  EVIDENCE_QUALITY: "evidence-quality",
  SAFETY_GATE: "safety-gate",
};

export const RESEARCH_DOMAINS = [
  {
    id: RESEARCH_DOMAIN_IDS.WEATHER,
    label: "Weather",
    fallbackSummary: "Weather exposure has not been confirmed from available evidence.",
  },
  {
    id: RESEARCH_DOMAIN_IDS.TERRAIN,
    label: "Terrain",
    fallbackSummary: "Terrain context is not yet visible in the returned evidence.",
  },
  {
    id: RESEARCH_DOMAIN_IDS.ACCESS,
    label: "Access",
    fallbackSummary: "Access, stopping, and approach constraints need review.",
  },
  {
    id: RESEARCH_DOMAIN_IDS.INFRASTRUCTURE,
    label: "Infrastructure",
    fallbackSummary: "Infrastructure proximity needs confirmation from evidence.",
  },
  {
    id: RESEARCH_DOMAIN_IDS.ENERGY_UTILITIES,
    label: "Energy / Utilities",
    fallbackSummary: "Energy and utility constraints are not fully established.",
  },
  {
    id: RESEARCH_DOMAIN_IDS.WATER_FLOODING,
    label: "Water / Flooding",
    fallbackSummary: "Watercourse and flood context requires evidence review.",
  },
  {
    id: RESEARCH_DOMAIN_IDS.PLANNING_CONTEXT,
    label: "Planning / Context",
    fallbackSummary: "Planning and surrounding-area context has not been fully checked.",
  },
  {
    id: RESEARCH_DOMAIN_IDS.SITE_HAZARDS,
    label: "Site Hazards",
    fallbackSummary: "Candidate hazards appear after the agent completes site research.",
  },
  {
    id: RESEARCH_DOMAIN_IDS.EVIDENCE_QUALITY,
    label: "Evidence Quality",
    fallbackSummary: "Evidence provenance and confidence should be checked before use.",
  },
  {
    id: RESEARCH_DOMAIN_IDS.SAFETY_GATE,
    label: "Safety Gate",
    fallbackSummary: "Human review is required before dispatch or work planning.",
  },
];
