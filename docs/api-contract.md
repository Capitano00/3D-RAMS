# AgentCore Invocation Contract

3D-RAMS exposes the local demo runtime through the AgentCore dev server. The frontend calls the Vite proxy path `/agentcore/invocations`, which forwards to AgentCore Runtime `/invocations`.

The runtime is local-first. It does not require AWS credentials, Google keys, live planning portals, hosted infrastructure, real site data, or private documents.

AgentVerse and ASI:ONE should not call AgentCore directly in the current architecture. The intended cross-platform path is documented in [agentverse-agentcore-adapter-contract.md](agentverse-agentcore-adapter-contract.md): AgentVerse entry agent confirms intake, the adapter validates and signs/invokes AgentCore, then delivery returns to the entry agent.

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/ping` | Confirms the AgentCore runtime is reachable. |
| `POST` | `/invocations` | Runs the coordinate-to-briefing agent workflow. |

## Ping Response

The AgentCore dev server returns a health object that includes:

```json
{
  "status": "Healthy"
}
```

## Invocation Request

The request body must use the AgentCore envelope:

```json
{
  "input": {
    "fixturePack": "public-lambeth-thames",
    "includePlanningFixture": true,
    "simulateMapFailure": false,
    "useBedrock": false
  }
}
```

Known `input` fields:

| Field | Type | Notes |
| --- | --- | --- |
| `siteName` | string | Optional site label for briefing and visualizer output. |
| `latitude` | number | Decimal degrees, `-90` to `90`. Defaults to fixture coordinate when omitted. |
| `longitude` | number | Decimal degrees, `-180` to `180`. Defaults to fixture coordinate when omitted. |
| `goal` | string | User goal for the pre-visit briefing. |
| `fixturePack` | string or null | Optional cached fixture pack id, for example `public-lambeth-thames`. |
| `fixture_pack` | string or null | Backward-compatible alias for `fixturePack`. |
| `includePlanningFixture` | boolean | Defaults to `true`. Set `false` to test missing planning/context behavior. |
| `simulateMapFailure` | boolean | Defaults to `false`. Set `true` to force the geospatial fallback path. |
| `useBedrock` | boolean | Defaults to `true`. Bedrock is used only when runtime environment settings enable it. |
| `additionalRequest` | string | Optional user instruction. Unsafe RAMS/work-approval claims are blocked. |
| `upstream` | object | Optional upstream metadata from AgentVerse, ASI:ONE, or another entry agent. |

## Invocation Response

The response keeps the AgentCore output envelope:

```json
{
  "output": {
    "reportStatus": "review_required",
    "workflowMode": "cached_public_fixture",
    "run": {}
  }
}
```

Important `output.run` fields:

| Field | Meaning |
| --- | --- |
| `upstream` | Optional entry-agent/session metadata passed through the adapter. |
| `request` | Normalized request summary used by the agent. |
| `runtime` | Fixture mode, Bedrock mode, fallback reason, and live-call status. |
| `location` | Resolved site label and coordinate. |
| `scene` | 3D scene configuration for the frontend viewer. |
| `hazards` | Candidate hazards extracted from cached/synthetic evidence. |
| `annotations` | 3D annotation data with confidence labels. |
| `briefing` | Human-review RAMS-style briefing summary, checks, and limitations. |
| `evidence` | Evidence register with source/status/context. |
| `trace` | Ordered tool timeline with statuses, source ids, evidence ids, and fallback reasons. |
| `safety` | Safety gate result and triggered rules. |
| `architecture` | Data for the in-app Architecture + Workflow visualizer. |

## Safety And Data Boundary

The runtime returns a pre-visit review pack for human review only. It does not produce certified RAMS, emergency guidance, work approval, legal advice, or a competent-person replacement.

Do not send real client data, private site records, access-controlled planning documents, secrets, API keys, or AWS credentials to the runtime or issue tracker.
