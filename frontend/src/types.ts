export type AppMode = 'GLOBE' | 'DESCENT' | 'EXPLORATION';

export type AgentId = string;

export type AgentStatus = 'idle' | 'resolving' | 'complete' | 'error';

export interface Agent {
  id: AgentId;
  name: string;
  fullName: string;
  status: AgentStatus;
  confidence: number;
  vintage: string;
  warning?: string;
}

export interface RiskZone {
  id: string;
  category: 'flooding' | 'infrastructure' | 'energy' | 'immediate' | 'low_confidence';
  score: number; // 0.0 to 1.0
  points: [number, number][]; // [x, z] relative positions
  title: string;
  description: string;
  confidence: number;
  source: string;
}

export interface Annotation {
  id: string;
  title: string;
  type: string;
  level: 'hazard' | 'warning' | 'buffer';
  confidence: number;
  vintage: string;
  description: string;
  position: [number, number, number]; // [x, y, z] in ThreeJS world units or relative
  radius?: number; // for cylinder/sphere visual bounds
  evidenceThumb?: string; // procedurally drawn or inline svg/icon representation
}

export interface Site {
  name: string;
  lat: number;
  lng: number;
  elevation: number;
}

export interface RunResult {
  request?: Record<string, unknown>;
  runtime?: Record<string, unknown>;
  location?: Record<string, unknown>;
  scene?: Record<string, unknown>;
  hazards?: Record<string, unknown>[];
  annotations?: Record<string, unknown>[];
  briefing?: Record<string, unknown>;
  evidence?: Record<string, unknown>[];
  trace?: Record<string, unknown>[];
  safety?: Record<string, unknown>;
  architecture?: Record<string, unknown>;
  uiState?: {
    location?: Record<string, unknown>;
    scene?: Record<string, unknown>;
    annotations?: Record<string, unknown>[];
    hazards?: Record<string, unknown>[];
    evidence?: Record<string, unknown>[];
    trace?: Record<string, unknown>[];
    briefing?: Record<string, unknown>;
    safety?: Record<string, unknown>;
    sources?: Record<string, unknown>[];
  };
  [key: string]: unknown;
}

export interface ChatMessage {
  id: string;
  sender: 'user' | 'agent';
  text: string;
  timestamp: string;
  extractionCard?: {
    siteName: string;
    lat: number;
    lng: number;
    purpose: string;
    date: string;
    resolved: boolean;
    rawSite?: Site;
    backendRun?: RunResult;
  };
}
