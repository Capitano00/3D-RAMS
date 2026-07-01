# AgentCore Runtime Sidecar Migration Scorecard

This scorecard compares the current Lambda durable runtime with the local AgentCore-compatible sidecar scaffold. It is a migration planning artifact only; it does not claim that managed AgentCore Runtime is live.

## Current Recommendation

Use a hybrid path for now: keep Lambda/API Gateway as the hosted teammate runtime, and continue the AgentCore sidecar only as a parallel proof until managed Runtime, Observability, IAM, cost, and rollback gates are proven.

## Scorecard

| Area | Current Lambda durable runtime | AgentCore sidecar prototype | Current score |
| --- | --- | --- | --- |
| Functional parity | Full hosted flow exists: session, access gate, conversation router, location confirmation, durable tools, review pack, evidence, trace, safety. | Local sidecar now proves conversation, location candidate, explicit confirmation, review workflow, output shape, model-call metadata, and safety boundary. | Sidecar parity is good locally; not cloud-proven. |
| Lifecycle | Existing deployment, smoke scripts, CloudWatch logs, access-code control, and rollback to prior Lambda package. | Local process only. No managed Runtime lifecycle, deploy, versioning, or rollback proof yet. | Lambda stronger. |
| Memory | Bounded app-layer session memory, DynamoDB-backed session trace where configured, sanitized model context. | Same app-layer memory contract. AgentCore Memory intentionally disabled. | Equivalent app contract; AgentCore Memory unproven. |
| Tool governance | Durable runner enforces allowlisted tools, location confirmation before tools, model-call cap, timeout, evaluation loop, and safety gate. | Reuses the same durable runner and tests the no-tools-before-confirmation rule. | Equivalent locally. |
| Observability | Hosted logs and runtime trace exist; UI shows agent state, no-tool reason, model calls, trace/evidence. | Local response includes durable-run trace and sidecar metadata; no managed AgentCore Observability yet. | Lambda stronger for live ops. |
| Security | Existing access code, server-side Bedrock only, private upload path, no frontend AWS credentials. | Local-only, no access-code exposure, no AWS resources, no frontend path. Future deployment security not reviewed. | Sidecar safe locally; deployment security unknown. |
| Cost/complexity | Known Lambda/API Gateway/Bedrock shape with existing budget guardrails; operational packaging complexity is known. | Local cost is zero. Managed Runtime cost, IAM, deployment shape, and debugging complexity are not validated. | Keep sidecar local until cost gate. |
| Demo clarity | Teammate path is already stable and demonstrable in browser. | Sidecar is useful for architecture proof but not a judge-facing product path yet. | Lambda stronger for demo. |

## Decision Options

### Keep Lambda

Choose this if teammate testing, final demo, and submission stability are the priority. Lambda remains the source of truth; AgentCore stays as architecture evidence only.

### Hybrid

Choose this next if we want AWS learning without risking the hosted MVP. Run managed AgentCore as a separate endpoint only after an approval gate, smoke it with no teammate traffic, and compare traces/output against Lambda.

### Continue AgentCore Migration

Choose this only after a managed Runtime proof passes:

- local sidecar parity;
- CLI/CDK/tooling readiness;
- IAM and network policy review;
- cost guardrail;
- no private data retention issue;
- Observability proof;
- rollback plan;
- quality review.

## Required Gate Before Any Managed AgentCore Deployment

Do not deploy automatically. A future deployment proposal must list:

- exact AWS resources to create or change;
- region and account profile assumptions without exposing private account details;
- IAM permissions and trust boundaries;
- expected costs and budget controls;
- data retention and memory policy;
- rollback plan;
- smoke tests for health, unsafe request, location confirmation, confirmed review workflow, model-call cap, and no frontend traffic switch.

## Current Decision

Recommendation: **hybrid later, keep Lambda primary now**.

Reasoning: the sidecar proves enough local runtime parity to justify a later managed AgentCore spike, but Lambda remains stronger on live lifecycle, observability, access control, and demo reliability.
