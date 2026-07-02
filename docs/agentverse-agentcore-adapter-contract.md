# AgentVerse To AgentCore Adapter Contract

This contract fixes the boundary between the AgentVerse entry agent and the AgentCore supervisor runtime. It is local-first and contains no AWS credentials, API keys, private user data, or live site records.

The adapter is not the workflow backend. It validates launch readiness, maps payloads, and later owns IAM/signing for AgentCore invocation.

Implementation note: the separate ASI:ONE proof of concept has been imported into this repository as `app/asi_one_entry_agent` and `agentverse/hosted_adapter.py`. See [agentverse-asi-one-runtime.md](agentverse-asi-one-runtime.md). Real runtime ARNs and AgentVerse secrets stay outside this public repo.

## Entry Agent To Adapter

The entry agent sends a confirmed intake payload only after the user has approved the launch.

```json
{
  "caseId": "case_demo_fixture_001",
  "conversationId": "agentverse-session-id",
  "entryAgentId": "rams-entry-agent",
  "confirmedByUser": true,
  "reportAccess": {
    "schemaVersion": "3d-rams.report-access.v1",
    "mode": "asi_session",
    "sessionId": "agentverse-session-id"
  },
  "intake": {
    "locationText": "near 8 Albert Embankment, Lambeth",
    "locationCandidate": {
      "label": "Lambeth Thames public fixture",
      "lat": 51.4908,
      "lng": -0.1216,
      "confidence": 0.82
    },
    "areaScope": {
      "type": "radius",
      "meters": 800
    },
    "userGoal": "pre-visit site risk and planning context",
    "userNotes": "Focus on flood context, access, and public interface constraints.",
    "materials": [
      {
        "materialId": "asio_material_site_access_plan",
        "sourceSystem": "asio",
        "type": "application/pdf",
        "label": "Site access plan",
        "summary": "Uploaded by the ASI user for this case.",
        "caseId": "case_demo_fixture_001",
        "sizeBytes": 4096,
        "access": {
          "mode": "asio_authorized_reference",
          "expiresAt": "2026-06-30T18:00:00Z",
          "sessionId": "agentverse-session-id",
          "retrievalUrl": "<short-lived ASI retrieval URL supplied out of band>"
        }
      }
    ]
  },
  "runtimeOptions": {
    "fixturePack": "public-lambeth-thames",
    "useBedrock": false,
    "includePlanningFixture": true,
    "simulateMapFailure": false
  }
}
```

Required launch fields:

| Field | Requirement |
| --- | --- |
| `confirmedByUser` | Must be `true`. |
| `intake.locationText` or `intake.locationCandidate` | At least one location clue is required. |
| `intake.areaScope` | Required so the supervisor can plan the review area. |
| `intake.userGoal` | Required so the supervisor can align evidence to the report purpose. |

## Optional Postcodes.io Candidate Resolver

The ASI:ONE entry agent can resolve direct UK full postcode or outcode prompts before supervisor launch when `ENABLE_POSTCODES_IO_RESOLVER=true` is set on the server. It is default-off; local Demo1 and tests must remain no-network unless this flag is enabled or a test fake is injected.

Successful lookups populate the existing `intake.locationCandidate` shape with `label`, `lat`, `lng`, `source` (`Postcodes.io postcode lookup` or `Postcodes.io outcode lookup`), `confidence`, `dataMode`, `postcodeKind`, postcode/outcode labels, and bounded public administrative context such as district, region, and country when Postcodes.io returns it. Full postcodes use higher candidate confidence than outcodes because outcodes are broader centroids.

Provider errors, rate limits, malformed responses, or no matches fail soft back to the deterministic text candidate/clarification behavior. The resolver is not authoritative site evidence, does not verify the actual worksite, does not run in the browser, and does not trigger supervisor tools until the user confirms the candidate.

## Adapter To AgentCore

The adapter maps the confirmed intake into the AgentCore invocation envelope.

```json
{
  "input": {
    "caseId": "case_demo_fixture_001",
    "siteName": "Lambeth Thames public fixture",
    "latitude": 51.4908,
    "longitude": -0.1216,
    "goal": "pre-visit site risk and planning context",
    "fixturePack": "public-lambeth-thames",
    "useBedrock": false,
    "includePlanningFixture": true,
    "simulateMapFailure": false,
    "additionalRequest": "Focus on flood context, access, and public interface constraints.",
    "materials": [
      {
        "materialId": "asio_material_site_access_plan",
        "sourceSystem": "asio",
        "type": "application/pdf",
        "label": "Site access plan",
        "summary": "Uploaded by the ASI user for this case.",
        "caseId": "case_demo_fixture_001",
        "sizeBytes": 4096,
        "access": {
          "mode": "asio_authorized_reference",
          "expiresAt": "2026-06-30T18:00:00Z",
          "sessionId": "agentverse-session-id",
          "retrieval": {
            "method": "retrieval_url",
            "provided": true
          }
        }
      }
    ],
    "upstream": {
      "source": "AGENTVERSE",
      "adapterVersion": "agentverse-agentcore-adapter-v0",
      "conversationId": "agentverse-session-id",
      "entryAgentId": "rams-entry-agent",
      "confirmedByUser": true,
      "areaScope": {
        "type": "radius",
        "meters": 800
      },
      "locationConfidence": 0.82,
      "materialCount": 1,
      "reportAccess": {
        "schemaVersion": "3d-rams.report-access.v1",
        "mode": "asi_session",
        "caseId": "case_demo_fixture_001",
        "sessionId": "agentverse-session-id",
        "authorizedCaseIds": ["case_demo_fixture_001"]
      }
    }
  }
}
```

Material references are forwarded as structured `materials`. They are not flattened into `additionalRequest`; the supervisor material-ingestion phase validates case/session binding, expiry, type, and size before producing safe summaries, citations, evidence, and trace reasons. When ASI supplies `access.retrievalUrl` or `access.apiHandle`, normal adapter output keeps only `access.retrieval.method` plus `provided: true`; raw URLs, handles, tokens, and signed URLs are not echoed.

The local AgentCore runtime currently preserves this metadata as request context and returns the existing visualization run under `output.run`.

## Bounded Hosted Planner Context

The hosted OpenAI-compatible planner does not receive the full adapter payload. Before the planner prompt is built, the supervisor reduces entry-derived state to `3d-rams.hosted-planner-context.v1`.

Allowed fields are limited to `caseId`, confirmed location label or safe candidate summary, `areaScope`, `userGoal`, fixture/data mode, material counts/status/type/source metadata, and public-safe runtime or dogfood summary fields that are already present.

Forbidden fields must not reach planner prompts, trace summaries, structured reports, or report-store summaries: raw turn text, raw conversation/session history, raw session ids, access codes, tokens, signed URLs, retrieval URLs, API handles, private material content, private notes, client/private documents, and hidden reasoning. Report lookup authorization still uses `reportAccess`, but stored/public artifacts keep only redacted markers and hashed bindings.

## Pending Intake Recovery Boundary

Current pending intake is process-local by design. `asi_one_entry_agent` keeps `_PENDING_INTAKES` and bounded conversation state only long enough to bridge a clarification/confirmation chat turn to the next turn in the same runtime process. `agentverse/hosted_adapter.py` keeps a matching process-local hint so a hosted confirmation message can include the pending intake. This is Demo1 behavior, not durable session ownership.

The hosted failure mode is limited to this pre-launch gap: a runtime restart or cold start can lose a confirmation-ready draft before the user confirms and before the supervisor creates report/evidence output. After supervisor launch, recovery belongs to the case-correlated report/progress lookup contract, not pending-intake state.

Future recovery should live first in ASI/ASI:ONE session continuity. If hosted dogfood shows repeated user-facing loss that ASI/ASI:ONE cannot cover, 3D-RAMS may add only a short-lived pending-intake summary bound to ASI/ASI:ONE report-access metadata or a future case-correlated record. Do not use AgentCore Memory, `DYNAMODB_SESSION_TABLE`, `/api/session/start`, or a standalone 3D-RAMS web-session model for this boundary.

The maximum future summary shape is:

- `schemaVersion`, `pendingIntakeId`, `conversationRef` or ASI session reference, and optional future `caseId`;
- `entryAgentId`, `status: "awaiting_confirmation"`, timestamps, and short `expiresAt`;
- redacted or normalized location summary, area scope, and bounded user-goal summary;
- safe material ids/source ids and counts only;
- non-secret report-access binding reference for same-requester verification.

Never persist or echo raw user messages, raw site/client details beyond the safe summary, private material contents, retrieval URLs, API handles, signed URLs, access codes, raw ASI identity tokens, credentials, private planning notes, or certified RAMS/emergency/legal/work-approval claims. Expire pending summaries in minutes to hours and remove them on rejection, start-over, confirmation launch, or expiry.

## Report Lookup

Detailed report lookup is not authorized by `caseId` alone. The entry agent or frontend proxy must include `reportAccess` when requesting a stored report:

```json
{
  "frontendInvoke": true,
  "operation": "getReport",
  "caseId": "case_demo_fixture_001",
  "conversationId": "agentverse-session-id",
  "reportAccess": {
    "schemaVersion": "3d-rams.report-access.v1",
    "mode": "asi_session",
    "caseId": "case_demo_fixture_001",
    "sessionId": "agentverse-session-id",
    "authorizedCaseIds": ["case_demo_fixture_001"]
  }
}
```

The supervisor stores only hashed identity/session binding metadata with the report. If the lookup context is missing, expired, or does not match the stored binding, the response is `access_denied` and omits `run` and `structuredReport`. Local FieldBrief debugging may use `mode: "dev_local"` only as an explicit development bypass.

## AgentCore To Adapter

AgentCore returns the standard runtime envelope:

```json
{
  "output": {
    "reportStatus": "passed_with_caveats",
    "workflowMode": "cached_public_fixture",
    "run": {}
  }
}
```

`passed_with_caveats` means the independent review gate allowed delivery while keeping caveats visible. `review_required` is reserved for max-revision or unresolved review outcomes.

## Adapter To Entry Agent

The adapter returns a delivery payload suitable for ASI:ONE/AgentVerse:

```json
{
  "conversationId": "agentverse-session-id",
  "status": "passed_with_caveats",
  "workflowMode": "cached_public_fixture",
  "customerSummary": {
    "title": "Lambeth Thames public fixture",
    "headline": "Cached public-source review pack for early site scoping.",
    "summary": [],
    "priorityChecks": [],
    "safetyMessage": "Allowed as a non-certified pre-visit briefing that requires human review."
  },
  "deepReport": {
    "kind": "agentcore_run_payload",
    "runId": "demo1-local-run",
    "evidenceCount": 0,
    "traceCount": 0,
    "visualizationReady": true
  },
  "agentcoreOutput": {}
}
```

The entry agent can present the summary conversationally and link the user to the frontend visualization. It should not generate new unsupported risk claims outside the AgentCore-reviewed result.

## Local Mock Behavior

For local development:

- no AWS credentials are required;
- adapter functions run in-process;
- AgentCore can be invoked through `agentcore dev`;
- the frontend FieldBrief surface is a development/debug ASI entry simulation, not the production user entry;
- runtime output remains fixture-backed unless live integrations are explicitly enabled.

For cloud deployment:

- adapter transport must add IAM/signing;
- secrets must stay outside the public repo;
- errors must return to the entry agent as recoverable delivery or clarification states;
- long-running supervisor work may need async status and report retrieval rather than a single blocking request.
