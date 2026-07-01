export const OPERATIONAL_SOURCE_GROUPS = [
  {
    id: "location",
    label: "Location resolution",
    agent: "FieldBrief Orchestrator",
    sources: [
      "ASI:One / Chat Protocol user request",
      "OpenStreetMap Nominatim or enterprise geocoder",
      "Postcode/address/coordinate parser",
    ],
    output: "Resolved site label, WGS84 coordinate, ambiguity questions, review boundary",
    status: "integration-ready",
  },
  {
    id: "terrain",
    label: "3D terrain and base scene",
    agent: "Terrain Agent",
    sources: [
      "CesiumJS globe",
      "Cesium World Terrain via environment token when available",
      "Token-free ellipsoid/local overlays as fallback",
    ],
    output: "3D region model, camera target, local review area, terrain/fallback status",
    status: "partial",
  },
  {
    id: "weather",
    label: "Weather and wind",
    agent: "Weather Agent",
    sources: ["Open-Meteo", "Met Office DataPoint/DataHub where available", "Cached forecast snapshot"],
    output: "Rain, wind, temperature, severe-weather context, forecast timestamp",
    status: "planned-live",
  },
  {
    id: "water",
    label: "Water and flooding",
    agent: "Water Risk Agent",
    sources: ["Environment Agency flood map/open data", "OpenStreetMap waterways", "Local drainage/flood reports"],
    output: "Flood zones, river-edge context, drainage notes, water proximity warnings",
    status: "planned-live",
  },
  {
    id: "access",
    label: "Access and stopping",
    agent: "Access Agent",
    sources: ["OpenStreetMap roads/paths", "local authority transport data", "uploaded method statements"],
    output: "Access route, stopping constraints, pedestrian/vehicle approach notes",
    status: "planned-live",
  },
  {
    id: "infrastructure",
    label: "Infrastructure and utilities",
    agent: "Infrastructure Agent",
    sources: [
      "OpenStreetMap infrastructure tags",
      "public asset registers where available",
      "uploaded utility drawings or enterprise asset records",
    ],
    output: "Rail/road/bridge corridors, utility proximity, OHL/energy context, verification warnings",
    status: "partial",
  },
  {
    id: "planning",
    label: "Planning and land context",
    agent: "Planning Context Agent",
    sources: ["Local authority planning portals/open data", "brownfield registers", "uploaded planning PDFs"],
    output: "Planning history, brownfield flags, nearby constraints, evidence snippets",
    status: "cached-now",
  },
  {
    id: "evidence",
    label: "Evidence and audit",
    agent: "Evidence Agent",
    sources: ["Uploaded PDFs/images", "public-source metadata", "tool trace and run records"],
    output: "Evidence register, source status, fallback reason, traceable report sections",
    status: "live-now",
  },
];

export const AGENT_WORKFLOW_STEPS = [
  {
    id: "parse",
    label: "Parse request",
    description: "Extract place, coordinate, activity, timing, and missing critical details from the ASI:One chat.",
  },
  {
    id: "resolve",
    label: "Resolve area",
    description: "Resolve the site and define a bounded region so unrelated surrounding areas stay visually separate.",
  },
  {
    id: "collect",
    label: "Collect source signals",
    description: "Run domain agents for weather, water, access, infrastructure, utilities, planning, terrain, and uploads.",
  },
  {
    id: "visualize",
    label: "Build 3D review model",
    description: "Render the region boundary and risk layers as an inspectable Cesium scene.",
  },
  {
    id: "report",
    label: "Generate review pack",
    description: "Produce a human-review report with evidence, confidence, fallback, limitations, and next checks.",
  },
];
