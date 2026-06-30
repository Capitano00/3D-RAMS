# 3D-RAMS AgentVerse Entry Runtime

This runtime was imported from the `onboardAgentCore/app/MyAgent` proof of concept and renamed for its actual role. It is the AgentCore-side runtime that the AgentVerse hosted adapter can invoke for the public `@3d-rams` entry agent.

It is separate from `app/rams_supervisor_runtime`, which remains the 3D-RAMS supervisor/report runtime.

`supervisor_adapter.py` is the entry-side contract adapter for the supervisor runtime. It validates confirmed AgentVerse intake payloads, maps them to the supervisor `/invocations` envelope, and normalizes supervisor output into entry-agent delivery payloads.

## Runtime Role

- Accept chat-style prompts or Bedrock-style message payloads from the AgentVerse hosted adapter.
- Accept structured frontend/proxy payloads with confirmed intake and launch the supervisor runtime.
- Use a fast Bedrock-backed intake path for entry-agent clarification and confirmation when configured.
- Preserve AgentCore session/user identity so memory can be used when configured.
- Stay thin: intake and delivery UX live here, while deeper site-review orchestration belongs in `rams_supervisor_runtime`.

## LLM-First Intake

The entry turn path supports the ADR 0011 LLM-first mode with deterministic fallback:

```bash
ENTRY_INTAKE_MODE=llm_first
ENTRY_INTAKE_MODEL_ID=amazon.nova-micro-v1:0
ENTRY_INTAKE_FALLBACK=deterministic
ENTRY_INTAKE_MAX_RETRIES=1
ENTRY_INTAKE_TIMEOUT_SECONDS=20
```

When `runtimeOptions.useBedrock` is false or `ENTRY_INTAKE_MODE=deterministic`, the runtime uses the deterministic coordinator directly. When LLM intake is enabled but Bedrock credentials, timeout, or model JSON validation fail, the runtime falls back to deterministic intake and returns `entryAgent.intakeMode: "fallback"` plus a `fallbackReason`. Invalid model output is never allowed to launch the supervisor.

## Cloud Supervisor Handoff

Set the supervisor runtime ARN in the deployed entry runtime environment:

```bash
RAMS_SUPERVISOR_RUNTIME_ARN=arn:aws:bedrock-agentcore:<region>:<account-id>:runtime/<runtime-id>
```

The entry runtime maps confirmed intake with `supervisor_adapter.py`, invokes the supervisor runtime, and returns the supervisor run plus entry delivery payload. Do not commit the real ARN.

Report lookup also routes through the supervisor runtime. The entry runtime forwards `operation: "getReport"` with an explicit `reportAccess` object so the supervisor can validate ASI/ASI:ONE identity or authorized session binding before returning stored `run` or `structuredReport` data. `caseId` is only a correlation id; it is not a report access token.

## Local Development

The deployed/runtime entry agent uses AWS/Bedrock and Strands for meaningful model responses:

```bash
agentcore dev --runtime asi_one_entry_agent --skip-deploy --no-browser --no-traces --logs --port 8082
```

For explicit no-AWS local testing, `local_entry_flow.py` still provides a deterministic local ASI:ONE substitute. It is no longer the default frontend path; set `VITE_USE_LOCAL_ASIONE=true` only when local testing is intended. Local report lookup uses an explicit `dev_local` access context and must not be described as production authorization.

Optional Exa MCP tooling is disabled by default. Enable it only when live outbound network use is intended:

```bash
ENTRY_AGENT_ENABLE_EXA_MCP=true
```

## Public Repo Boundary

Do not commit AWS credentials, AgentVerse keys, seed phrases, runtime ARNs, account IDs, or private user/session content. Use environment variables in the deployment environment.
