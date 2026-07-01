import { create } from 'zustand';
import { Site, Agent, Annotation, AppMode, ChatMessage, RiskZone, RunResult, AgentStatus } from '../types';

export interface SiteStore {
  mode: AppMode;
  setMode: (mode: AppMode) => void;
  selectedSite: Site;
  setSelectedSite: (site: Site) => void;
  agents: Agent[];
  setAgents: (agents: Agent[]) => void;
  annotations: Annotation[];
  setAnnotations: (annotations: Annotation[]) => void;
  selectedAnnotation: Annotation | null;
  setSelectedAnnotation: (annotation: Annotation | null) => void;
  observationPack: string[];
  toggleInObservationPack: (id: string) => void;
  resolutionProgress: number;
  setResolutionProgress: (progress: number) => void;
  weatherActive: boolean;
  setWeatherActive: (active: boolean) => void;
  customCoordinates: string;
  setCustomCoordinates: (coords: string) => void;
  triggerDescent: (site: Site) => void;
  applyRunResult: (run: RunResult, fallbackSite?: Site | null) => void;
  lastRun: RunResult | null;
  predefinedSites: Site[];
  
  // Cesium matrix synchronization
  fixedToEnuMatrix: number[] | null; // Float64Array or 16-element array
  setFixedToEnuMatrix: (matrix: number[] | null) => void;
  
  // Camera update callback to pass to ThreeJS overlay
  cesiumCameraMatrix: number[] | null; // 16-element camera view matrix
  setCesiumCameraMatrix: (matrix: number[] | null) => void;
  
  cesiumFrustum: { fovy: number; aspect: number; near: number; far: number } | null;
  setCesiumFrustum: (frustum: { fovy: number; aspect: number; near: number; far: number } | null) => void;

  riskZones: RiskZone[];
  setRiskZones: (zones: RiskZone[]) => void;

  // Chat Integration
  chatOpen: boolean;
  setChatOpen: (open: boolean) => void;
  chatHistory: ChatMessage[];
  setChatHistory: (history: ChatMessage[]) => void;
  addChatMessage: (msg: ChatMessage) => void;
}

const DEFAULT_SITES: Site[] = [
  { name: 'Birmingham Rail Corridor', lat: 52.4862, lng: -1.8904, elevation: 110 },
  { name: 'London Thameslink Hub', lat: 51.5074, lng: -0.1278, elevation: 25 },
  { name: 'Snowdon Grid Interconnect', lat: 53.0685, lng: -4.0763, elevation: 840 },
  { name: 'Edinburgh Tram Extension', lat: 55.9533, lng: -3.1883, elevation: 75 },
];

const INITIAL_CHAT: ChatMessage[] = [
  {
    id: 'msg-1',
    sender: 'user',
    text: 'I need to visit Birmingham Rail Corridor tomorrow for a survey. What should I know?',
    timestamp: '11:00 AM',
  },
  {
    id: 'msg-2',
    sender: 'agent',
    text: 'I resolved the initial location candidate and prepared a pre-visit review workflow for human confirmation.',
    timestamp: '11:00 AM',
    extractionCard: {
      siteName: 'Birmingham Rail Corridor',
      lat: 52.4862,
      lng: -1.8904,
      purpose: 'Structural Survey & Engineering Inspection',
      date: 'Tomorrow (Jul 1, 2026)',
      resolved: true,
      rawSite: { name: 'Birmingham Rail Corridor', lat: 52.4862, lng: -1.8904, elevation: 110 },
    }
  }
];


const INITIAL_AGENTS: Agent[] = [
  {
    id: 'WEATHER',
    name: 'Weather Agent',
    fullName: 'Atmospheric Dynamics Sub-Agent',
    status: 'idle',
    confidence: 0.94,
    vintage: 'METAR Real-time feed',
  },
  {
    id: 'IFA',
    name: 'IFA Agent',
    fullName: 'Electromagnetic & Field Exposure Sub-Agent',
    status: 'idle',
    confidence: 0.88,
    vintage: '12-mo LiDAR & Grid Cache',
    warning: 'Using static model cache',
  },
  {
    id: 'OHL',
    name: 'OHL Agent',
    fullName: 'Overhead Line Geometry Sub-Agent',
    status: 'idle',
    confidence: 0.97,
    vintage: 'Network Rail Vector Model v4.2',
  },
  {
    id: 'PLANNING',
    name: 'Planning Supervisor',
    fullName: 'Multi-Agent Autonomous Coordinator',
    status: 'idle',
    confidence: 0.99,
    vintage: '3D RAMs Core v3.0',
  },
];

const MOCK_ANNOTATIONS: Record<string, Annotation[]> = {
  'Birmingham Rail Corridor': [
    {
      id: 'IFA-01',
      title: 'IFA Exposure Corridor',
      type: 'IFA',
      level: 'hazard',
      confidence: 0.89,
      vintage: 'LiDAR Cache 2026',
      description: 'Localized electromagnetic exposure context detected near a sub-station transformer feed. Treat as a review item requiring competent-person verification before planning work.',
      position: [-15, 3, 10],
      radius: 18,
    },
    {
      id: 'OHL-01',
      title: 'OHL Strike-Distance Advisory',
      type: 'OHL',
      level: 'warning',
      confidence: 0.98,
      vintage: 'Vector Model 4.2',
      description: 'Calculated clearance height of 5.1 meters under overhead line conductor segment OHL-B11. Risk of vertical encroachment during scaffolding or heavy plant maneuvers.',
      position: [12, 10, -8],
      radius: 8,
    },
    {
      id: 'WEATHER-01',
      title: 'Moisture Dispersion Hazard',
      type: 'WEATHER',
      level: 'buffer',
      confidence: 0.92,
      vintage: 'METAR Station EGBB',
      description: 'Moderate rain and high wind vectors causing directional moisture drift. High probability of surface run-off across trench zones. Local structural shoring verification required.',
      position: [2, 1, 15],
      radius: 12,
    },
  ],
  'London Thameslink Hub': [
    {
      id: 'IFA-02',
      title: 'Grid Node Feed Exposure',
      type: 'IFA',
      level: 'warning',
      confidence: 0.85,
      vintage: 'LiDAR Cache 2026',
      description: 'Elevated magnetic flux density surrounding cable terminal node J-109. Measured value at 1.8 mG. Field verification recommended before manual excavation operations.',
      position: [5, 2, -15],
      radius: 10,
    },
    {
      id: 'OHL-02',
      title: 'Catenary Wire Sag Variance',
      type: 'OHL',
      level: 'hazard',
      confidence: 0.72,
      vintage: 'Vector Model 4.2',
      description: 'Low confidence clearance detected. High ambient air temperature has induced a thermal sag expansion of 0.45 meters. Clearance currently estimated at 4.9m above rail level.',
      position: [-8, 8, 2],
      radius: 15,
    },
  ],
  'Snowdon Grid Interconnect': [
    {
      id: 'WEATHER-02',
      title: 'High Altitude Turbulence',
      type: 'WEATHER',
      level: 'hazard',
      confidence: 0.95,
      vintage: 'METAR Station EGOD',
      description: 'High wind context across pylon terrain. Cable sway, structural stress, and loose-material risks require human review against live site controls before dispatch.',
      position: [0, 12, 0],
      radius: 30,
    },
  ],
  'Edinburgh Tram Extension': [
    {
      id: 'OHL-03',
      title: 'OHL Feeder Buffer Incursion',
      type: 'OHL',
      level: 'warning',
      confidence: 0.96,
      vintage: 'Vector Model v4.2',
      description: 'Horizontal clearance zone buffer (3.0 meters) overlaps with planned temporary work platform outline WP-4. Uncontrolled contact risk flagged.',
      position: [20, 6, -5],
      radius: 10,
    },
  ],
};

export const MOCK_RISK_ZONES: Record<string, RiskZone[]> = {
  'Birmingham Rail Corridor': [
    {
      id: 'risk-flood-1',
      category: 'flooding',
      score: 0.65,
      points: [[10, 5], [25, 8], [20, 25], [5, 18]],
      title: 'Trench Drainage Runoff Zone',
      description: 'High risk of moisture pooling and water ingress in secondary rail trenches.',
      confidence: 0.91,
      source: 'METAR Real-Time Feed & DEM Scan'
    },
    {
      id: 'risk-energy-1',
      category: 'energy',
      score: 0.85,
      points: [[-22, -15], [-8, -15], [-8, -2], [-22, -2]],
      title: 'OHL Electrostatic Induction Field',
      description: 'Substation electromagnetic context requiring verification of asset records and site controls before any work planning.',
      confidence: 0.88,
      source: 'LiDAR & Grid Cache 2026'
    },
    {
      id: 'risk-immediate-1',
      category: 'immediate',
      score: 0.95,
      points: [[-5, 10], [5, 10], [8, 20], [-8, 20]],
      title: 'Active High-Voltage Conflict Hotzone',
      description: 'Immediate mechanical hazard area beneath cable sag threshold.',
      confidence: 0.97,
      source: 'Network Rail Vector Model v4.2'
    }
  ],
  'London Thameslink Hub': [
    {
      id: 'risk-infra-1',
      category: 'infrastructure',
      score: 0.7,
      points: [[-25, 5], [-12, 5], [-12, 18], [-25, 18]],
      title: 'Brutalist Concrete Substructure Node',
      description: 'High density reinforcement zone under Thameslink platforms.',
      confidence: 0.85,
      source: 'Subsurface CAD Blueprint'
    },
    {
      id: 'risk-flood-2',
      category: 'flooding',
      score: 0.45,
      points: [[5, -20], [20, -15], [15, -5], [2, -10]],
      title: 'Thames-Adjacent Tide Water Buffer',
      description: 'Slight groundwater seepage risk in baseline track levels.',
      confidence: 0.79,
      source: 'Environment Agency Live Feed'
    }
  ],
  'Snowdon Grid Interconnect': [
    {
      id: 'risk-lowconf-1',
      category: 'low_confidence',
      score: 0.55,
      points: [[15, 10], [30, 12], [25, 25], [10, 20]],
      title: 'Gale-Force Jitter Segment',
      description: 'High wind loading zone with unverified terrain elevation files.',
      confidence: 0.65,
      source: 'Unverified Cadastral Satellite Scan'
    },
    {
      id: 'risk-energy-2',
      category: 'energy',
      score: 0.9,
      points: [[-18, 5], [-5, 8], [-10, 22], [-22, 18]],
      title: 'Grid Interconnect Transformer Compound',
      description: 'Power-transformer context flagged for competent-person review and asset-record verification.',
      confidence: 0.95,
      source: 'National Grid Asset Registry'
    }
  ],
  'Edinburgh Tram Extension': [
    {
      id: 'risk-immediate-2',
      category: 'immediate',
      score: 0.8,
      points: [[-10, 12], [2, 15], [0, 28], [-12, 24]],
      title: 'Temporary Work Platform Encroachment',
      description: 'Active scaffolding corridor conflicting with tram contact wire clearance.',
      confidence: 0.94,
      source: 'Edinburgh Tram Vector Model v4.2'
    },
    {
      id: 'risk-infra-2',
      category: 'infrastructure',
      score: 0.6,
      points: [[15, -15], [28, -12], [22, -2], [10, -5]],
      title: 'Municipal Feeder Trench Base',
      description: 'Heavy reinforcement and concrete masonry layers.',
      confidence: 0.88,
      source: 'City Council Utility Survey'
    }
  ]
};

export function mapRiskZoneToAnnotation(zone: RiskZone): Annotation {
  let sumX = 0;
  let sumZ = 0;
  zone.points.forEach(pt => {
    sumX += pt[0];
    sumZ += pt[1];
  });
  const avgX = sumX / zone.points.length;
  const avgZ = sumZ / zone.points.length;

  let type = 'IFA';
  if (zone.category === 'flooding') type = 'WEATHER';
  else if (zone.category === 'immediate') type = 'OHL';

  let level: 'hazard' | 'warning' | 'buffer' = 'warning';
  if (zone.category === 'immediate') level = 'hazard';
  else if (zone.category === 'low_confidence') level = 'buffer';

  return {
    id: zone.id.toUpperCase(),
    title: zone.title,
    type,
    level,
    confidence: zone.confidence,
    vintage: zone.source,
    description: zone.description,
    position: [avgX, 0, avgZ],
    radius: 15
  };
}

function numberOrFallback(value: unknown, fallback: number): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function stringOrFallback(value: unknown, fallback: string): string {
  return typeof value === 'string' && value.trim() ? value : fallback;
}

function confidenceOf(item: Record<string, unknown>, fallback = 0.72): number {
  return Math.max(0.25, Math.min(0.99, numberOrFallback(item.confidence, fallback)));
}

function classifyCategory(item: Record<string, unknown>): RiskZone['category'] {
  const text = `${item.category || ''} ${item.title || ''} ${item.reason || ''} ${item.summary || ''}`.toLowerCase();
  if (text.includes('flood') || text.includes('water') || text.includes('rain')) return 'flooding';
  if (text.includes('utility') || text.includes('energy') || text.includes('power') || text.includes('electric')) return 'energy';
  if (text.includes('access') || text.includes('road') || text.includes('rail') || text.includes('infrastructure')) return 'infrastructure';
  if (text.includes('low') || text.includes('fallback') || text.includes('uncertain')) return 'low_confidence';
  return confidenceOf(item) < 0.7 ? 'low_confidence' : 'immediate';
}

function mapBackendHazardsToRiskZones(hazards: Record<string, unknown>[]): RiskZone[] {
  return hazards.slice(0, 8).map((hazard, index) => {
    const offset = index * 7;
    return {
      id: String(hazard.id || `hazard-${index + 1}`),
      category: classifyCategory(hazard),
      score: confidenceOf(hazard, 0.68),
      points: [
        [-18 + offset, -12 + (index % 2) * 8],
        [-6 + offset, -10 + (index % 3) * 5],
        [-8 + offset, 2 + (index % 2) * 6],
        [-22 + offset, 1 + (index % 3) * 4],
      ],
      title: stringOrFallback(hazard.title, `Review item ${index + 1}`),
      description: stringOrFallback(
        hazard.reason || hazard.summary || hazard.description,
        'Backend returned this item for human review. Verify source evidence and site conditions before dispatch.'
      ),
      confidence: confidenceOf(hazard),
      source: stringOrFallback(hazard.source || hazard.status, confidenceOf(hazard) < 0.7 ? 'Low-confidence backend result' : 'Agent review result'),
    };
  });
}

function mapBackendAnnotations(annotations: Record<string, unknown>[], hazards: RiskZone[]): Annotation[] {
  const mapped = annotations.slice(0, 12).map((annotation, index) => {
    const confidence = confidenceOf(annotation);
    return {
      id: String(annotation.id || `annotation-${index + 1}`),
      title: stringOrFallback(annotation.title, `Mapped review marker ${index + 1}`),
      type: stringOrFallback(annotation.type || annotation.category, confidence < 0.7 ? 'LOW_CONFIDENCE' : 'EVIDENCE'),
      level: confidence < 0.65 ? 'buffer' : confidence < 0.82 ? 'warning' : 'hazard',
      confidence,
      vintage: stringOrFallback(annotation.source || annotation.status, confidence < 0.7 ? 'Needs verification' : 'Backend mapped result'),
      description: stringOrFallback(
        annotation.reason || annotation.summary || annotation.description,
        'Mapped from backend annotation output. Use linked evidence and trace before acting on it.'
      ),
      position: [
        numberOrFallback(annotation.x, -16 + index * 6),
        numberOrFallback(annotation.y, confidence < 0.7 ? 3 : 6),
        numberOrFallback(annotation.z, -8 + (index % 4) * 7),
      ] as [number, number, number],
      radius: numberOrFallback(annotation.radius, confidence < 0.7 ? 12 : 16),
    };
  });

  if (mapped.length) return mapped;
  return hazards.map(mapRiskZoneToAnnotation);
}

function buildAgentsFromTrace(trace: Record<string, unknown>[] | undefined, runtime: Record<string, unknown> | undefined): Agent[] {
  if (!trace?.length) {
    return INITIAL_AGENTS.map((agent) => ({
      ...agent,
      status: runtime?.fallback ? 'error' : 'complete',
      warning: runtime?.fallback ? 'Fallback mode disclosed by backend' : agent.warning,
    }));
  }

  return trace.slice(0, 6).map((step, index) => {
    const statusText = String(step.status || '').toLowerCase();
    const status: AgentStatus = statusText.includes('fail') || statusText.includes('fallback')
      ? 'error'
      : statusText.includes('pending') || statusText.includes('run')
      ? 'resolving'
      : 'complete';
    const name = stringOrFallback(step.name || step.tool || step.agent, `Workflow Step ${index + 1}`);
    return {
      id: name.toUpperCase().replace(/[^A-Z0-9]+/g, '_'),
      name,
      fullName: stringOrFallback(step.summary, 'Allowlisted backend workflow step'),
      status,
      confidence: confidenceOf(step, status === 'error' ? 0.58 : 0.86),
      vintage: stringOrFallback(step.source || step.status, 'Agent trace'),
      warning: stringOrFallback(step.fallbackReason, ''),
    };
  });
}

export const useSiteStore = create<SiteStore>((set, get) => ({
  mode: 'GLOBE',
  setMode: (mode) => set({ mode }),
  selectedSite: DEFAULT_SITES[0],
  setSelectedSite: (site) => set({ selectedSite: site }),
  agents: INITIAL_AGENTS,
  setAgents: (agents) => set({ agents }),
  annotations: [...(MOCK_ANNOTATIONS[DEFAULT_SITES[0].name] || []), ...(MOCK_RISK_ZONES[DEFAULT_SITES[0].name] || []).map(mapRiskZoneToAnnotation)],
  setAnnotations: (annotations) => set({ annotations }),
  riskZones: MOCK_RISK_ZONES[DEFAULT_SITES[0].name] || [],
  setRiskZones: (riskZones) => set({ riskZones }),
  selectedAnnotation: null,
  setSelectedAnnotation: (selectedAnnotation) => set({ selectedAnnotation }),
  observationPack: [],
  toggleInObservationPack: (id) => set((state) => {
    const isIncluded = state.observationPack.includes(id);
    return {
      observationPack: isIncluded
        ? state.observationPack.filter(x => x !== id)
        : [...state.observationPack, id]
    };
  }),
  resolutionProgress: 0,
  setResolutionProgress: (resolutionProgress) => set({ resolutionProgress }),
  weatherActive: false,
  setWeatherActive: (weatherActive) => set({ weatherActive }),
  customCoordinates: '',
  setCustomCoordinates: (customCoordinates) => set({ customCoordinates }),
  predefinedSites: DEFAULT_SITES,
  
  fixedToEnuMatrix: null,
  setFixedToEnuMatrix: (fixedToEnuMatrix) => set({ fixedToEnuMatrix }),
  
  cesiumCameraMatrix: null,
  setCesiumCameraMatrix: (cesiumCameraMatrix) => set({ cesiumCameraMatrix }),
  
  cesiumFrustum: null,
  setCesiumFrustum: (cesiumFrustum) => set({ cesiumFrustum }),

  chatOpen: true,
  setChatOpen: (chatOpen) => set({ chatOpen }),
  chatHistory: INITIAL_CHAT,
  setChatHistory: (chatHistory) => set({ chatHistory }),
  addChatMessage: (msg) => set((state) => ({ chatHistory: [...state.chatHistory, msg] })),
  lastRun: null,
  applyRunResult: (run, fallbackSite = null) => {
    const uiState = run.uiState || {};
    const location = (uiState.location || run.location || {}) as Record<string, unknown>;
    const scene = (uiState.scene || run.scene || {}) as Record<string, unknown>;
    const center = (scene.center || {}) as Record<string, unknown>;
    const site: Site = {
      name: stringOrFallback(location.label || location.siteName || run.request?.siteName, fallbackSite?.name || 'Resolved site'),
      lat: numberOrFallback(location.latitude ?? center.latitude ?? run.request?.latitude, fallbackSite?.lat ?? 52.4862),
      lng: numberOrFallback(location.longitude ?? center.longitude ?? run.request?.longitude, fallbackSite?.lng ?? -1.8904),
      elevation: numberOrFallback(center.heightMeters ?? location.elevation, fallbackSite?.elevation ?? 45),
    };
    const hazards = mapBackendHazardsToRiskZones(((uiState.hazards || run.hazards || []) as Record<string, unknown>[]));
    const annotations = mapBackendAnnotations(((uiState.annotations || run.annotations || []) as Record<string, unknown>[]), hazards);
    const trace = ((uiState.trace || run.trace || []) as Record<string, unknown>[]);
    const runtime = (run.runtime || {}) as Record<string, unknown>;

    set({
      selectedSite: site,
      selectedAnnotation: null,
      mode: 'DESCENT',
      resolutionProgress: 0,
      fixedToEnuMatrix: null,
      riskZones: hazards.length ? hazards : MOCK_RISK_ZONES[site.name] || [],
      annotations: annotations.length ? annotations : MOCK_ANNOTATIONS[site.name] || [],
      agents: buildAgentsFromTrace(trace, runtime),
      weatherActive: true,
      lastRun: run,
    });
  },
  
  triggerDescent: (site) => {
    const zones = MOCK_RISK_ZONES[site.name] || [];
    const mappedAnnos = zones.map(mapRiskZoneToAnnotation);
    const siteAnnos = MOCK_ANNOTATIONS[site.name] || [
      {
        id: 'GEN-01',
        title: 'Custom Location Observation',
        type: 'IFA',
        level: 'warning',
        confidence: 0.82,
        vintage: 'Automated Satellite Scan',
        description: `Autonomous mapping executed over coordinates ${site.lat.toFixed(4)}, ${site.lng.toFixed(4)}. Baseline terrain resolved, low-confidence asset matching active. Field walk recommended.`,
        position: [0, 3, 0],
        radius: 14,
      }
    ];

    set({
      selectedSite: site,
      selectedAnnotation: null,
      mode: 'DESCENT',
      resolutionProgress: 0,
      fixedToEnuMatrix: null, // resets for new alignment calculation
      riskZones: zones,
      annotations: [...siteAnnos, ...mappedAnnos]
    });
    
    // Set status to resolving
    set({
      agents: INITIAL_AGENTS.map(agent => ({
        ...agent,
        status: 'resolving'
      }))
    });
    
    // Auto trigger rain for specific sites to showcase live weather system
    const shouldRain = site.name.includes('London') || site.name.includes('Birmingham');
    set({ weatherActive: shouldRain });
  },
}));
