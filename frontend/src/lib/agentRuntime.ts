import { RunResult, Site } from '../types';

const AGENT_ENDPOINT =
  import.meta.env.VITE_AGENT_ENDPOINT ||
  import.meta.env.VITE_AGENTCORE_ENDPOINT ||
  '/api/run';

type Intake = {
  query: string;
  site?: Site | null;
};

function parseCoordinate(query: string): { latitude?: number; longitude?: number } {
  const match = query.match(/([-+]?\d{1,2}(?:\.\d+)?)\s*,\s*([-+]?\d{1,3}(?:\.\d+)?)/);
  if (!match) return {};
  return {
    latitude: Number(match[1]),
    longitude: Number(match[2]),
  };
}

function normalizeAgentCoreEnvelope(payload: any): RunResult {
  return payload?.output?.run || payload?.output?.structuredReport || payload;
}

export function extractSiteFromRun(run: RunResult, fallback?: Site | null): Site {
  const rawLocation = (run.uiState?.location || run.location || {}) as Record<string, any>;
  const rawScene = (run.uiState?.scene || run.scene || {}) as Record<string, any>;
  const center = rawScene.center || {};
  return {
    name: String(rawLocation.label || rawLocation.siteName || run.request?.siteName || fallback?.name || 'Resolved site'),
    lat: Number(rawLocation.latitude ?? center.latitude ?? run.request?.latitude ?? fallback?.lat ?? 52.4862),
    lng: Number(rawLocation.longitude ?? center.longitude ?? run.request?.longitude ?? fallback?.lng ?? -1.8904),
    elevation: Number(center.heightMeters ?? rawLocation.elevation ?? fallback?.elevation ?? 45),
  };
}

export async function invokeReviewWorkflow({ query, site }: Intake): Promise<RunResult> {
  const coords = parseCoordinate(query);
  const input = {
    siteName: site?.name || (coords.latitude ? undefined : query),
    latitude: site?.lat ?? coords.latitude,
    longitude: site?.lng ?? coords.longitude,
    goal: query,
    additionalRequest: query,
    includePlanningFixture: true,
    simulateMapFailure: false,
    useBedrock: true,
    upstream: {
      entrySurface: 'ASI:One frontend console',
      confirmedByUser: true,
    },
  };

  const body = AGENT_ENDPOINT.includes('/agentcore') || AGENT_ENDPOINT.endsWith('/invocations')
    ? { input }
    : input;

  const response = await fetch(AGENT_ENDPOINT, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    throw new Error(`Agent workflow failed (${response.status})`);
  }

  return normalizeAgentCoreEnvelope(await response.json());
}
