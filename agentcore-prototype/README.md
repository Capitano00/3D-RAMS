# 3D-RAMS AgentCore Runtime Sidecar Prototype

This folder is the local sidecar prototype for evaluating whether the 3D-RAMS FieldBrief agent should later move to Amazon Bedrock AgentCore Runtime.

It is not the live teammate path. The hosted MVP remains:

```text
Amplify frontend -> API Gateway -> Lambda/FastAPI -> durable runner -> Bedrock/tools/state
```

This sidecar is a parallel proof path:

```text
local /invocations harness -> FieldBrief conversation contract -> durable runner -> local fixtures/tools
```

Current status:

- The prototype is shaped for a future AgentCore Runtime proof in `eu-west-2`.
- No managed AgentCore runtime is live for the public demo yet.
- The hosted MVP still uses Lambda/FastAPI as the active adapter.
- No Amplify app, API Gateway route, Lambda function, DynamoDB table, S3 bucket, access-code setting, or frontend API base URL is changed by this prototype.
- The prototype keeps memory disabled at the AgentCore service layer until retention and privacy are reviewed; bounded session memory remains in the app layer.
- The local sidecar harness processes runs inline by default so smoke tests return a terminal guard, clarification, confirmation, or review-pack state rather than a transient background-worker state.
- The sidecar now exposes the AgentCore HTTP scaffold endpoints: `POST /invocations` for JSON requests and `GET /ping` for health.
- `POST /invocations` accepts the AgentCore-style `prompt` field and the existing 3D-RAMS `message` field. It returns a non-streaming JSON response with the full 3D-RAMS route/run details under `details`.
- Sidecar smokes default to `useBedrock=false`; model calls require an explicit request and environment support.

## What This Proves

The sidecar proves the Module 1 runtime contract locally:

1. A user sends a postcode or latitude/longitude site-visit request.
2. The agent parses intent through the existing FieldBrief contract.
3. The agent creates a source-labelled location candidate.
4. The run stops before map/evidence/risk/review tools and asks for confirmation.
5. A separate `confirm_location` sidecar action starts the review workflow.
6. The completed output includes a review pack, risk cards, evidence, trace, model-call metadata, and the safety boundary.

Chat-only text such as `yes` does not count as location confirmation. Confirmation must use the candidate id via the explicit sidecar action.

## How It Differs From Lambda Runtime

| Area | Current hosted MVP | AgentCore sidecar prototype |
| --- | --- | --- |
| Traffic | Live teammate path behind Amplify/API Gateway/Lambda | Local-only proof path; no teammate traffic |
| Entry | `/api/conversation/message`, `/api/runs`, `/api/runs/{id}/confirm-location` | `POST /invocations` with `message`/`prompt`, plus `action=confirm_location` |
| State | Lambda memory plus configured session trace adapters | Local process memory using the same app-layer session contract |
| Memory | Bounded working memory; no raw access codes in model context | Same app-layer bounded memory; AgentCore Memory disabled |
| Tools | Existing durable runner and allowlisted tools | Reuses the same durable runner and allowlisted tools |
| Safety | No certified RAMS, work approval, or emergency guidance | Same safety boundary, exercised before model/tool work |
| Deployment | Existing hosted AWS resources | No AWS resources created or changed |

## Intended AgentCore Path

1. Install the AgentCore CLI separately:

   ```powershell
   npm.cmd install -g @aws/agentcore
   agentcore --help
   ```

2. Use the checked-in files as a scaffold and generate the authoritative AgentCore project config with the CLI. The intended CLI shape is HTTP protocol, Bedrock model provider, CodeZip build, and `memory none`.
3. Keep `memory none` for the first AgentCore Runtime proof.
4. Deploy a parallel runtime endpoint.
5. Smoke-test it without switching the hosted frontend.
6. Add Observability before considering AgentCore Memory.
7. Switch traffic only after quality review.

Any real AgentCore deployment must be proposed as a separate approval gate first, including exact resources, cost/security impact, rollback plan, and expected smoke tests.

## Local Smoke

Run the sidecar smoke without deploying AWS resources:

```powershell
python agentcore-prototype\smoke_sidecar.py
```

The smoke checks:

- help/clarification stays conversation-only;
- unsafe certification or work-approval text is blocked before model calls;
- coordinate prompts wait for location confirmation before tools run;
- explicit `confirm_location` action runs the review workflow and returns the durable-run output shape;
- chat-only `yes` does not run review tools;
- follow-up questions use bounded session memory;
- `/invocations` and `/ping` match the AgentCore HTTP scaffold.

The sidecar input shapes are:

```json
{
  "message": "I want to visit 50.825351, -0.125125 tomorrow for a roof survey.",
  "useBedrock": false
}
```

```json
{
  "action": "confirm_location",
  "runId": "run-from-previous-response",
  "candidateId": "candidate-from-locationCandidates",
  "useBedrock": false
}
```

`prompt` may be used instead of `message` for AgentCore-style invocation tests.

## Files

| Path | Purpose |
| --- | --- |
| `app/fieldbrief_agent/main.py` | Minimal AgentCore-side entrypoint wrapper around the existing 3D-RAMS conversation and confirmation contract, with `/invocations` and `/ping` HTTP endpoints. |
| `app/fieldbrief_agent/pyproject.toml` | Dependency declaration for a CodeZip-style Python prototype. |
| `agentcore/agentcore.template.json` | Public-safe project config template. |
| `agentcore/aws-targets.template.json` | Public-safe AWS target template. |
| `smoke_sidecar.py` | Local deterministic scaffold smoke. |
| `migration-scorecard.md` | Lambda versus AgentCore sidecar migration scorecard and recommendation options. |

## Safety Boundary

The prototype must preserve the current MVP controls:

- access control remains outside the model path;
- no tools before confirmed location;
- no certified RAMS, emergency guidance, or approval-to-work claims;
- no frontend AWS credentials;
- no raw access codes, secrets, uploaded file contents, or private client data in memory/logs.
