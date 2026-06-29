# ADR 0001: AgentVerse Entry Layer And AgentCore Runtime Boundary

## Status

Accepted for Demo1 architecture direction.

## Context

3D-RAMS currently runs as a local-first FastAPI and React demo. The backend has a deterministic agent loop with inspectable tool steps, evidence, trace rows, fallback behavior, and a safety gate. Amazon Bedrock is used only as an optional briefing-generation step when explicitly configured.

The workflow is expected to become more complex than a simple prompt-to-response agent. It needs structured inputs, fixture and future source loading, hazard extraction, 3D annotation generation, evidence tracking, fallback handling, safety decisions, evaluation harnesses, and eventually production observability.

AgentVerse, or an AgentCore Registry-style catalog and entry surface, is useful for making an agent discoverable and invokable. It is not the right place to own the full 3D-RAMS workflow orchestration, safety policy, evaluation harness, and deployment lifecycle.

## Decision

Use AgentCore as the target runtime family for the complex 3D-RAMS agent workflow, then expose or register the resulting agent through AgentVerse or the relevant AgentCore registry/catalog surface.

AgentVerse should be treated as the entry and discovery layer. AgentCore should be treated as the runtime, observability, policy, and deployment boundary for production-shaped execution.

The current Demo1 codebase should remain local-first until the workflow and harness are clear enough to migrate deliberately. Do not claim that Demo1 is already deployed on AgentCore or AWS.

## Current Implementation Status

The repository does not currently use the AgentCore CLI.

There is no `agentcore/agentcore.json`, `agentcore/aws-targets.json`, AgentCore CLI scaffold, Dockerfile, CDK app, SAM template, Terraform stack, App Runner config, or AWS deployment pipeline in the repo.

The current backend exposes:

- `GET /health`;
- `POST /api/run`.

AgentCore Runtime custom deployment examples require an AgentCore-compatible invocation contract, including `/invocations` and `/ping` endpoints for custom HTTP agents, plus packaging and AWS runtime deployment. The current API shape is close enough to adapt, but it is not deploy-ready for AgentCore without a wrapper or endpoint migration.

## Consequences

Positive:

- Keeps Demo1 runnable without cloud credentials or live map keys.
- Preserves the existing evidence, trace, fallback, and safety boundaries while the workflow is still evolving.
- Leaves room to choose between AgentCore CLI scaffolding, custom AgentCore Runtime deployment, or another AWS hosting path after the harness is specified.
- Keeps AgentVerse focused on discoverability and invocation rather than internal orchestration.

Tradeoffs:

- A future AWS migration will need explicit deployment work, not only configuration.
- The agent API contract may need an adapter from `/api/run` to AgentCore Runtime's invocation shape.
- Production observability, persistence, registry publication, IAM, and safety policy integration remain future work.

## Next Review Trigger

Revisit this decision after the 3D-RAMS agent workflow and harness are documented. The next review should decide:

- whether to use AgentCore CLI scaffolding or a custom AgentCore Runtime package;
- how to map the existing trace and evidence model into AgentCore Observability and CloudWatch;
- how to wrap or migrate `/api/run` into an AgentCore-compatible invocation endpoint;
- what should be registered in AgentVerse or the AgentCore registry/catalog surface;
- which parts remain deterministic local code, which parts use Bedrock, and which parts become managed AWS services.
