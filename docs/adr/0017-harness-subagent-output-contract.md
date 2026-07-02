# ADR 0017: Harness Subagent Output Contract

## Status

Proposed for implementation planning.

## Context

ADR 0002 defines a supervisor workflow that dispatches specialist subagents and assembles a review-gated report. ADR 0003 moves the implementation into AgentCore CLI and Harness conventions. ADR 0007 adds a mandatory supervisor reasoning pass over collected evidence.

The current hosted workflow proves that the supervisor can call deployed Harness subagents. However, the returned payloads are not yet consistent across Harnesses. The supervisor currently normalizes several non-standard responses, producing trace entries such as:

- `harness_returned_non_standard_trace`;
- `review_harness_returned_non_dict_safety`;
- fallback evidence or finding records synthesized by the supervisor.

That normalization is acceptable for early smoke testing, but it is not a stable contract. It creates ambiguity for:

- supervisor reasoning;
- structured report generation;
- independent review;
- frontend report rendering;
- external evaluation;
- future CloudWatch trace mapping.

The team needs one explicit Harness output contract before adding more live subagents or depending on Harness outputs for product-quality reports.

## Decision

Define a shared Harness subagent output contract that every 3D-RAMS Harness must satisfy.

Each Harness may have a domain-specific `data` object, but every successful Harness response must include a common envelope:

```json
{
  "schemaVersion": "3d-rams.harness-output.v1",
  "subagent": {
    "name": "planning_subagent",
    "harness": "rams_planning_harness",
    "phase": "initial_parallel_research"
  },
  "status": "ok | warning | fallback | blocked",
  "summary": "Short inspectable summary of what this Harness produced.",
  "data": {},
  "evidence": [],
  "findings": [],
  "trace": [],
  "references": [],
  "warnings": [],
  "errors": [],
  "metadata": {
    "caseId": "case_id",
    "fixturePack": "public-lambeth-thames",
    "mode": "fixture | live | hybrid",
    "generatedAt": "ISO-8601 timestamp"
  }
}
```

The supervisor must validate this envelope before using a Harness response. If validation fails, the supervisor may normalize the response for demo continuity, but it must mark the normalization as fallback in `trace`, `dataQuality.gaps`, and the structured report.

## Required Common Fields

- `schemaVersion`: versioned output schema.
- `subagent.name`: stable planner-visible subagent name.
- `subagent.harness`: deployed Harness identifier.
- `status`: execution status from the Harness perspective.
- `summary`: short safe explanation, suitable for logs and UI.
- `data`: domain-specific structured payload.
- `evidence`: evidence records produced or transformed by the Harness.
- `findings`: candidate findings or domain observations produced by the Harness.
- `trace`: inspectable steps, not hidden chain-of-thought.
- `references`: source references backing evidence and findings.
- `warnings`: recoverable issues or data-quality caveats.
- `errors`: blocking or partial-failure details.
- `metadata`: case, mode, and timing information.

## Domain Payloads

The first implementation should map each existing Harness into `data` as follows:

- `geospatial_subagent`: resolved location, geospatial features, scene configuration.
- `planning_subagent`: planning context, source references, planning evidence.
- `hazard_subagent`: candidate hazards/findings with evidence and source references.
- `annotation_subagent`: frontend-ready annotations tied to findings.
- `briefing_subagent`: briefing summary, priority checks, report-ready wording, evidence list.
- `review_guardrail`: review decision, safety level, pass/fail status, reviewer notes.

Domain payloads may evolve, but the common envelope must remain stable within the schema version.

## Finding Contract

Any Harness that returns candidate findings should use:

```json
{
  "id": "stable-finding-id",
  "title": "Human-readable finding title",
  "category": "planning | hazard | access | environment | heritage | open_web | other",
  "description": "Finding statement for report use.",
  "confidence": "high | medium | low | unknown",
  "sourceIds": [],
  "evidenceIds": [],
  "traceIds": [],
  "humanReviewRequired": true
}
```

The frontend may render `title`, `category`, `description`, and `confidence` directly. The supervisor may enrich findings with reasoning and review metadata, but should not need to guess field names such as `type`, `note`, or `rawTrace`.

## Trace Contract

Harness trace entries should be explicit, bounded, and UI/log safe:

```json
{
  "id": "trace-id",
  "name": "load_planning_context",
  "status": "ok | warning | fallback | blocked",
  "summary": "Loaded cached planning context fixture.",
  "sourceIds": [],
  "evidenceIds": [],
  "policyDecision": {
    "tool_name": "load_planning_context",
    "decision": "allow | skip | reject | downgrade",
    "reason_code": "runtime_path_allowed",
    "source": "supervisor_runtime"
  },
  "startedAt": "ISO-8601 timestamp",
  "endedAt": "ISO-8601 timestamp",
  "durationMs": 42
}
```

`policyDecision` is optional for older Harnesses, but when present it is limited to `tool_name`, `decision`, `reason_code`, and `source`. It records public-safe execution-policy decisions only; trace must not include hidden chain-of-thought, secrets, private notes, raw credentials, signed URLs, or confidential material content.

## Relationship To Existing ADRs

- ADR 0002 defines the supervisor/subagent/review workflow.
- ADR 0003 defines the AgentCore CLI and Harness migration.
- ADR 0007 defines the supervisor reasoning pass that consumes Harness outputs.
- ADR 0016 defines hosted smoke parity; smoke should eventually assert this Harness output contract.

## Consequences

Positive:

- Reduces supervisor fallback normalization.
- Gives the frontend a stable report data surface.
- Makes review and external evaluation easier to implement.
- Gives hosted smoke tests concrete schema checks.

Tradeoffs:

- Existing Harness prompts and adapters need updates.
- The supervisor must maintain validation and backward-compatible fallback during migration.
- Tests must cover both valid Harness output and malformed Harness fallback.

## Acceptance Criteria

- Each deployed 3D-RAMS Harness returns `schemaVersion: 3d-rams.harness-output.v1`.
- The supervisor validates the common envelope before consuming Harness data.
- Non-standard Harness output is marked as fallback and is visible in trace/data-quality outputs.
- Risk cards, evidence, reasoning, and structured report generation no longer depend on ad hoc field guessing.
- Hosted smoke can assert that all required Harness responses are contract-compliant.

## Non-Goals

- Do not standardize every possible domain field in this ADR.
- Do not block local deterministic demo execution while Harnesses are migrated.
- Do not expose hidden chain-of-thought or private source material.
- Do not claim certified RAMS, legal approval, emergency guidance, or approval-to-work.
