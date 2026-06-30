# ADR 0006: Amplify App Framework Hosting

## Status

Accepted for implementation planning.

## Context

The `main` worktree already has an AWS hosted MVP path for the earlier FastAPI/Lambda demo:

- Amplify manual frontend hosting;
- API Gateway HTTP API;
- Lambda/FastAPI backend;
- DynamoDB session trace;
- S3 upload presign;
- CloudWatch logs;
- optional Bedrock server-side model calls.

The Amplify part is currently managed by `deploy/deploy-amplify.ps1`. That script builds a ZIP from `frontend/dist`, creates or finds an Amplify app and branch, calls `create-deployment`, uploads the ZIP to the deployment URL, and starts the deployment. This works for a quick hosted MVP, but it is not an Amplify App Framework project. There is no `amplify/` app source tree, no `amplify.yml`, no app-framework build contract, and no Git-connected Amplify deployment configuration.

The new AgentCore-oriented line of work needs a cleaner hosted frontend path. The frontend should be able to deploy from source in a repeatable way and point at either:

- the signed AgentCore entry proxy for the cloud workflow; or
- an explicit local-only path when `VITE_USE_LOCAL_ASIONE=true`.

Manual ZIP deployment should become a fallback/debug mechanism, not the primary hosted path.

## Decision

Move hosted frontend deployment from Amplify manual ZIP hosting to an Amplify App Framework-style configuration.

The repository should define the frontend hosting contract in source control through Amplify build configuration and environment-variable expectations. Amplify should build the React/Vite frontend from `frontend/`, publish `frontend/dist`, and inject only public client configuration such as the signed proxy URL. AWS credentials, AgentCore runtime ARNs, AgentVerse secrets, and private deploy handoff files must remain outside the public repository.

The first implementation should not move AgentCore runtime deployment into Amplify. Amplify remains the frontend host. AgentCore CLI/CDK remains responsible for runtimes and Harnesses. The signed proxy remains the safe browser-to-AgentCore bridge.

## Target Hosting Model

```mermaid
flowchart LR
    Git["Git branch"] --> Amplify["Amplify App Framework build"]
    Amplify --> UI["Hosted React/Vite frontend"]
    UI --> Proxy["Signed AgentCore entry proxy"]
    Proxy --> Entry["Cloud asi_one_entry_agent"]
    Entry --> Supervisor["Cloud rams_supervisor_runtime"]
    Supervisor --> Harnesses["AgentCore Harness subagents"]
```

Amplify owns:

- source-connected frontend build and hosting;
- branch-specific environment variables;
- static asset delivery and SPA rewrite behavior;
- frontend domain management.

Amplify does not own:

- AgentCore runtime deployment;
- Harness deployment;
- AgentVerse hosted adapter secrets;
- IAM users, access keys, or runtime ARNs committed to the repo.

## Required Repository Changes

Add an Amplify build configuration that:

- uses `frontend/` as the app root;
- installs frontend dependencies with the repository's lockfile strategy;
- runs the Vite production build;
- publishes `frontend/dist`;
- preserves SPA fallback routing to `index.html`;
- exposes required public env names without defaulting to secrets.

Expected frontend environment variables:

```bash
VITE_CLOUD_ENTRY_PROXY_URL=https://<signed-proxy-domain>/invoke
VITE_USE_LOCAL_ASIONE=false
VITE_CESIUM_ION_TOKEN=
```

Local-only variables such as `VITE_AGENTCORE_URL` and `VITE_AGENTCORE_PROXY_TARGET` may remain documented for development, but they should not be required for the hosted Amplify app.

The existing `deploy/deploy-amplify.ps1` should be retained temporarily as a fallback manual-deploy tool and clearly marked as legacy/manual hosting. It should not be the default deployment path after this ADR is implemented.

## Migration Plan

1. Add Amplify App Framework configuration.
   - Add `amplify.yml` or the Amplify-supported equivalent at the repo root.
   - Configure build commands to run from `frontend/`.
   - Confirm the published artifact path is `frontend/dist`.

2. Configure Amplify app/branch.
   - Connect Amplify to the intended GitHub branch.
   - Set `VITE_CLOUD_ENTRY_PROXY_URL` in Amplify branch environment variables.
   - Keep `VITE_USE_LOCAL_ASIONE=false` for hosted demos.

3. Preserve backend separation.
   - Keep AgentCore deployment under AgentCore CLI/CDK.
   - Keep the signed proxy deployment separate from Amplify unless a later ADR chooses a managed hosting target for it.
   - Do not copy AWS credentials, AgentCore ARNs, or AgentVerse secrets into frontend code.

4. Update docs and runbooks.
   - Update hosted frontend deployment instructions to prefer Amplify source-connected deployment.
   - Keep manual ZIP deployment documented as fallback only.
   - Record the new hosted URL and CORS/proxy expectations in public-safe docs without secrets.

5. Verify the hosted app.
   - Confirm Amplify build succeeds from clean checkout.
   - Confirm static assets, Cesium assets, and SPA reloads work.
   - Confirm frontend calls the signed proxy, not local AgentCore dev paths.
   - Confirm the returned supervisor payload still renders map, evidence, trace, safety, and briefing sections.

## Consequences

Positive:

- Hosted frontend deployment becomes repeatable from source.
- The public demo no longer depends on local manual ZIP packaging.
- Branch-specific previews become easier to manage.
- Frontend hosting stays separated from AgentCore runtime deployment.

Tradeoffs:

- Requires one-time Amplify app/branch setup.
- Requires hosted environment variables to be configured in Amplify.
- Requires a separate signed proxy deployment target before the hosted frontend can run the full cloud workflow.
- Existing manual deploy scripts need to be maintained or clearly deprecated during transition.

## Acceptance Criteria

- A clean branch can build and deploy the frontend through Amplify App Framework configuration.
- The hosted app uses `VITE_CLOUD_ENTRY_PROXY_URL` and does not send `localAsiOne: true` by default.
- Manual Amplify ZIP deployment remains available only as a documented fallback.
- No AWS credentials, account ids, runtime ARNs, AgentVerse secrets, or private deployment summaries are committed.
- The hosted UI can render a cloud workflow response containing `run`, `structuredReport`, trace, safety, and visualization data.

## Next Review Trigger

Revisit this ADR after the first source-connected Amplify deployment is working and the team decides whether the signed proxy should remain a separate deployment artifact, move behind API Gateway/Lambda, or be absorbed into a future Amplify backend configuration.
