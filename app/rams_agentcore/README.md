# 3D-RAMS AgentCore Runtime

This directory started from an AgentCore CLI scaffold and now contains the deployable 3D-RAMS runtime package.

# Layout

The generated application code lives at the agent root directory. At the root, there is a `.gitignore` file, an
`agentcore/` folder which represents the configurations and state associated with this project. Other `agentcore`
commands like `deploy`, `dev`, and `invoke` rely on the configuration stored here.

## Agent Root

The main entrypoint is `main.py`. It uses the AgentCore SDK `@app.entrypoint` decorator and delegates invocation handling to `three_d_rams.agentcore_adapter`.

The current migration preserves the existing deterministic 3D-RAMS workflow under `three_d_rams/`. Bedrock remains optional and environment-controlled.

`three_d_rams.agentverse_adapter` is a local contract adapter for the AgentVerse entry-agent boundary. It validates confirmed intake payloads, maps them to AgentCore `/invocations`, and normalizes AgentCore output into entry-agent delivery payloads. It does not run the supervisor workflow and should remain thinner than the AgentCore runtime.

Runtime-required fixture data is packaged under `fixtures/` so local mock and cached-public modes are available to AgentCore packaging.

## Environment Variables

| Variable | Required | Description |
| --- | --- | --- |
| `LOCAL_DEV` | No | Set to `1` to use `.env.local` instead of AgentCore Identity. |
| `ENABLE_BEDROCK` | No | Set to `true` only when AWS credentials and model access are ready. Defaults to deterministic fallback. |
| `RUNTIME_DATA_MODE` | No | Use `fixture_first` for Demo1 and no-AWS validation. |

# Developing locally

If installation was successful, a virtual environment is already created with dependencies installed.

Run `source .venv/bin/activate` before developing.

From the repository root, start the local runtime server on port 8080 with:

`agentcore dev --runtime rams_agentcore --skip-deploy --no-browser --no-traces --logs --port 8080`

In a new terminal, you can invoke that server with:

`agentcore invoke --dev '{"input":{"fixturePack":"public-lambeth-thames","useBedrock":false}}'`

The demo UI targets AgentCore by default through the Vite proxy at `/agentcore/invocations`. Start the frontend with `npm run dev` from `frontend/` after AgentCore is listening on port 8080.

For the AgentVerse/ASI:ONE entry-agent payload shape, see `docs/agentverse-agentcore-adapter-contract.md`.

# Deployment

After providing credentials and passing the repo verification stack, `agentcore deploy` can deploy the project into Amazon Bedrock AgentCore.

Use `agentcore invoke` to invoke your deployed agent.
