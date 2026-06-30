# ADR 0009: External Agentic Evaluation Harness

## Status

Accepted for first LLM-backed tool implementation.

## Context

The current repository has deterministic evaluation scripts for Demo1 and local checks. These prove that the AgentCore runtime can generate expected fixture-backed outputs, preserve the safety boundary, and serve the frontend without AWS credentials.

ADR 0002 also calls for independent review agents to verify factual support and inference quality before report release. The current runtime has a safety gate and a `reviewGate` placeholder, but it does not yet have a full independent agentic review loop.

The project needs an intermediate capability: an external agentic evaluator that can inspect complete supervisor outputs and score them against a rubric. This should help the team improve reasoning, evidence support, safety language, and visualization readiness without immediately blocking the user-facing demo path.

## Decision

Add external agentic evaluation as a sidecar evaluation workflow before promoting it into the synchronous supervisor review gate.

The first implementation runs outside the user-facing request path. It accepts a saved or freshly generated supervisor output and produces an evaluation artifact. It uses a cheap Bedrock text model as the evaluator. Local rule checks remain inside the tool as guardrails and structured input to the model, but they are not presented as the main evaluation mode.

This is different from the in-workflow review gate:

- external agentic eval is for development, regression testing, and quality scoring;
- the review gate is for runtime release control.

The external evaluator can later become one input to the runtime review gate after its rubric and failure modes are stable.

## Evaluation Position

```mermaid
flowchart LR
    Supervisor["Supervisor output"] --> Eval["External agentic evaluator"]
    Eval --> Artifact["Evaluation artifact"]
    Artifact --> Team["Developer / reviewer feedback"]

    Supervisor -. future .-> Review["Runtime independent review gate"]
```

## Evaluation Contract

Input:

```json
{
  "run": {},
  "structuredReport": {},
  "expectedBehavior": {
    "mustStayWithinSafetyBoundary": true,
    "requiresVisualizationPayload": true,
    "requiresEvidenceReferences": true
  }
}
```

Output:

```json
{
  "schemaVersion": "3d-rams.agentic-eval.v1",
  "caseId": "case-or-run-id",
  "mode": "llm",
  "overall": {
    "status": "pass",
    "score": 0.92,
    "summary": "Report is visualization-ready with inspectable evidence and trace references."
  },
  "rubric": [],
  "recommendedFixes": []
}
```

The evaluator output must be safe for public logs and CI artifacts. It must not contain secrets, private notes, hidden chain-of-thought, client data, or raw unredacted credentials.

## Initial Rubric

The first rubric evaluates:

- evidence support for findings;
- references on findings and report sections;
- unsupported certified RAMS, emergency, legal, medical, financial, or approval-to-work claims;
- fixture/fallback/live-source disclosure;
- data gaps and stale-source warnings;
- visualization payload completeness;
- trace completeness;
- consistency between `run`, `structuredReport`, `delivery`, and `reviewGate`;
- open-web signal labeling when open-web data is present.

## Implementation Guidance

First implementation:

1. Add a repo-level runner such as `scripts/evaluate-agentic.py`.
2. Reuse the current supervisor runtime to generate a fixture-backed output when no input file is provided.
3. Add local rubric checks as guardrails and model input.
4. Use the cheapest practical Bedrock text model for the model-backed evaluator.
5. Write artifacts under `docs/evaluation-results/` or another existing evaluation output path.
6. Keep CI optional at first, or run only deterministic checks in CI.
7. Add tests for rubric scoring and unsafe claim detection.

Future implementation:

- add an `app/rams_eval_harness/` if the evaluator needs AgentCore Harness controls beyond the current sidecar Bedrock call;
- feed evaluator findings into the runtime review gate;
- compare current output against previous accepted artifacts for regression detection;
- add scenario-specific expected outcomes.

## Non-Goals

- Do not block user-facing report generation in the first implementation.
- Do not replace the runtime review gate.
- Do not require Tavily or live source integrations for the evaluator.
- Do not produce certified compliance, legal approval, emergency guidance, or approval-to-work judgments.

## Consequences

Positive:

- Lets the team improve report quality in parallel with runtime workflow work.
- Creates measurable quality signals before the independent review loop is production-shaped.
- Keeps experimental evaluators out of the main demo path until stable.

Tradeoffs:

- Adds another artifact type to maintain.
- Model-backed evaluation may be nondeterministic and cost-bearing.
- The team must avoid treating eval pass as certified professional approval.

## Acceptance Criteria

- A local agentic eval tool can make one cheap Bedrock model call when AWS credentials are configured.
- Evaluation output includes pass/warn/fail status, rubric scores, and actionable findings.
- The evaluator checks evidence references, safety language, data gaps, visualization readiness, and trace completeness.
- Optional LLM-backed eval remains explicit and environment-controlled.
- No secrets, private notes, hidden chain-of-thought, or unsupported professional claims are emitted.

## LLM Evaluation Configuration

The evaluator defaults to exactly one Bedrock model call from the CLI:

```bash
scripts/evaluate-agentic.py
```

AWS credentials must be configured outside the repository. Unit tests can use `AGENTIC_EVAL_MOCK_RESPONSE=true` to avoid live model calls.

Recommended low-cost defaults:

```bash
AGENTIC_EVAL_MODEL_ID=amazon.nova-micro-v1:0
AGENTIC_EVAL_MAX_TOKENS=700
AGENTIC_EVAL_TEMPERATURE=0
```

The evaluator output records model id, region, mode, latency, public-safe LLM findings, and local guardrail rubric results, but not credentials or hidden reasoning.
