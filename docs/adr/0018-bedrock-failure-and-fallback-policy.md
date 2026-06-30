# ADR 0018: Bedrock Failure And Fallback Policy

## Status

Proposed for implementation planning.

## Context

The hosted demo now supports a frontend `useBedrock` toggle. The no-Bedrock path is the stable smoke path:

- frontend calls the signed proxy;
- proxy invokes `asi_one_entry_agent`;
- entry agent invokes `rams_supervisor_runtime`;
- supervisor dispatches Harness subagents;
- report is persisted and rendered by case id.

When `useBedrock=false`, the workflow can still use deterministic planning, fixtures, Harness outputs, and structured report assembly. This path is appropriate for hackathon demo stability.

When `useBedrock=true`, the intended behavior is to enable LLM-backed entry intake, supervisor planning, evidence reasoning, or briefing where configured. However, the current cloud path may still fail with runtime errors if model access, request shape, timeout, output parsing, or a Bedrock adapter fails.

The project needs an explicit policy for Bedrock failures so that enabling LLM behavior does not make the whole hosted workflow brittle or ambiguous.

## Decision

Bedrock is an enhancement path, not a hard dependency for the hosted demo.

For the current product/demo phase, any Bedrock-backed step must fail soft unless the step is explicitly configured as required. A Bedrock failure should produce a structured fallback result, preserve traceability, and continue the workflow when a deterministic or fixture-backed substitute can produce a safe non-certified report.

The default policy is:

- `useBedrock=false`: do not call Bedrock; use deterministic or fixture-backed behavior.
- `useBedrock=true`: attempt configured Bedrock steps, but fall back to deterministic behavior on recoverable failure.
- unrecoverable validation or safety failures: do not launch or publish the report; return a clear blocked status.

Bedrock failures must never appear to the user as an unexplained HTTP 500 when a safe fallback or clear blocked response is possible.

## Failure Classes

Recoverable failures:

- model access denied;
- timeout;
- throttling;
- transient network or AWS service error;
- invalid model JSON;
- schema validation failure on model output;
- model output missing optional report enhancements.

Recoverable failures should set:

```json
{
  "status": "fallback",
  "fallbackReason": "bedrock_timeout | bedrock_access_denied | invalid_model_json | schema_validation_failed",
  "bedrockRequested": true,
  "bedrockUsed": false
}
```

Unrecoverable failures:

- unsafe request;
- missing confirmed intake;
- invalid location or area scope after validation;
- material access denied where the material is required;
- review gate blocks report publication;
- no deterministic fallback exists for a required step.

Unrecoverable failures should return a structured blocked response and should not produce a normal report payload.

## Runtime Modes

The supervisor and entry agent should expose explicit runtime mode fields:

```json
{
  "runtime": {
    "bedrockRequested": true,
    "bedrockEnabled": true,
    "bedrockUsed": false,
    "plannerMode": "deterministic | bedrock | fallback",
    "briefingMode": "disabled | bedrock | fallback",
    "activeAgentMode": "deterministic-planner | bedrock-planner | fallback-planner",
    "fallbackReason": "invalid_model_json"
  }
}
```

The frontend may expose these fields as status chips, but the user-facing summary should remain concise.

## Step Policy

Entry intake:

- LLM-first entry is desirable per ADR 0011.
- Invalid LLM output must not launch the supervisor.
- Deterministic intake may be used as fallback if it can produce a valid clarification or confirmation state.

Supervisor planning:

- Bedrock planner may propose a subagent plan.
- If the plan is invalid, the supervisor falls back to the deterministic bounded Harness plan.
- The fallback must be visible in trace.

Briefing generation:

- Bedrock may improve wording.
- If Bedrock fails, the system may use deterministic briefing assembled from evidence and Harness summaries.

Reasoning:

- ADR 0007 requires the reasoning pass to exist.
- If LLM reasoning fails, deterministic reasoning must be produced.

Review:

- Review safety decisions must not be silently bypassed.
- If a review Harness or LLM review fails and no deterministic safety fallback is available, the report must be blocked or marked `review_required`.

## Relationship To Existing ADRs

- ADR 0007 requires reasoning to be mandatory even when mocked or deterministic.
- ADR 0011 makes the entry experience LLM-first but keeps deterministic fallback.
- ADR 0016 requires hosted smoke parity; smoke should include both no-Bedrock and Bedrock-requested fallback cases.
- ADR 0017 defines the Harness output contract that Bedrock-backed Harnesses should still obey.

## Consequences

Positive:

- Keeps the hosted demo stable while Bedrock integration matures.
- Makes LLM failures inspectable instead of opaque.
- Allows the UI to expose Bedrock status without making it the only success path.
- Preserves safety boundaries.

Tradeoffs:

- The report quality may vary between Bedrock and fallback paths.
- Runtime payloads must clearly distinguish requested, used, disabled, and fallback model behavior.
- Tests must cover more failure modes.

## Acceptance Criteria

- `useBedrock=false` never attempts Bedrock calls.
- `useBedrock=true` can return a successful report with a visible fallback reason when Bedrock fails recoverably.
- Bedrock model output is schema-validated before it can affect launch, planning, reasoning, briefing, or review decisions.
- Unrecoverable safety or validation failures return structured blocked responses, not generic 500s.
- Trace, runtime, and structured report data-quality fields disclose Bedrock fallback.
- Hosted smoke includes at least one Bedrock-requested fallback scenario.

## Non-Goals

- Do not guarantee report quality parity between Bedrock and deterministic paths.
- Do not make Bedrock required for local no-AWS demo runs.
- Do not expose hidden chain-of-thought, secrets, raw model prompts containing private material, or credentials.
- Do not claim certified RAMS, legal approval, emergency guidance, or approval-to-work.
