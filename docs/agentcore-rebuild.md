# AgentCore Rebuild Plan

This document tracks the selected AgentCore path for 3D-RAMS.

The current hosted teammate MVP remains:

```text
Amplify frontend -> API Gateway -> Lambda/FastAPI -> Bedrock + tools + DynamoDB/S3/CloudWatch
```

The selected next runtime path is:

```text
Amplify frontend -> API Gateway/Lambda guard adapter -> AgentCore Runtime sidecar -> Bedrock + tools + trace
```

Managed AgentCore is not yet the live public runtime. The first implementation slice added an AgentCore-ready conversation boundary: bounded session memory, guarded routing, and an app-level memory contract.
The current sidecar scaffold implements the AgentCore HTTP shape locally with `POST /invocations` and `GET /ping`; it does not deploy an AgentCore runtime or receive teammate traffic.

## Why Not Direct Cutover Yet

The AgentCore path should be proven in parallel before any traffic switch. A direct cutover would risk breaking the working teammate MVP, so the safer route is a sidecar runtime proof with explicit smoke tests and review gates.

## Current Sidecar Contract

- Source: `agentcore-prototype/`.
- Protocol: HTTP JSON scaffold compatible with AgentCore Runtime's `/invocations` and `/ping` contract.
- Input: accepts AgentCore `prompt` or existing 3D-RAMS `message`; optional `sessionId`, `uploadedFileIds`, and explicit `useBedrock`.
- Confirmation: accepts `action=confirm_location` with `runId` and `candidateId` to start the same durable review workflow after candidate confirmation.
- Output: non-streaming JSON with `response`, `status`, and full route/run details under `details`.
- Default model behavior: `useBedrock=false` for local scaffold smoke; no model calls unless explicitly requested and enabled by environment.
- Memory: app-layer bounded session memory only; managed AgentCore Memory remains disabled.
- Traffic: no teammate or public traffic routes to this sidecar until a later quality-reviewed deployment gate.

## Decision Gates

| Gate | Required proof |
| --- | --- |
| 1. CLI/tooling | `agentcore --help` works locally and the project can run in `agentcore dev`. |
| 2. Runtime proof | A parallel AgentCore Runtime endpoint can answer a simple non-Bedrock request. |
| 3. Guard proof | Unsafe requests are blocked before model/tool execution. |
| 4. Memory proof | Follow-up/status questions use session context without broad long-term memory. |
| 5. Tool-loop proof | Location confirmation remains required before map/evidence/risk tools run. |
| 6. Observability proof | AgentCore/CloudWatch trace shows router, model, tool, evaluator, and safety phases. |
| 7. Quality review | Public docs, runtime claims, security, safety, cost, and rollback are reviewed before traffic switch. |

## First Prototype Scope

Use `agentcore-prototype/` as the sidecar source.

Default settings:

- CodeZip build;
- HTTP protocol with `/invocations` and `/ping`;
- Bedrock model provider;
- memory `none`;
- app-layer bounded memory only;
- no teammate traffic;
- no public production claim;
- no certified RAMS, emergency guidance, or approval-to-work claims.

Reference docs:

- [Amazon Bedrock AgentCore overview](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/what-is-bedrock-agentcore.html)
- [Get started with the AgentCore CLI](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-get-started-cli.html)
- [AgentCore Runtime HTTP protocol contract](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-http-protocol-contract.html)

## Deferred

- AgentCore Memory;
- AgentCore Gateway;
- AgentCore Browser;
- Cognito;
- public traffic switch;
- broad live geocoding/search.
