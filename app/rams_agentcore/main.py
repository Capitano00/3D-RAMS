from __future__ import annotations

from typing import Any

from three_d_rams.agentcore_adapter import handle_invocation, ping

try:
    from bedrock_agentcore.runtime import BedrockAgentCoreApp
except ImportError:  # Allows local tests without the AgentCore runtime package.
    BedrockAgentCoreApp = None


if BedrockAgentCoreApp is not None:
    app = BedrockAgentCoreApp()
    log = app.logger

    @app.entrypoint
    async def invoke(payload: dict[str, Any], context: Any) -> dict[str, Any]:
        log.info("Invoking 3D-RAMS AgentCore runtime.")
        return handle_invocation(payload)

else:
    app = None


def invoke_local(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return handle_invocation(payload)


def ping_local() -> dict[str, str]:
    return ping()


if __name__ == "__main__":
    if app is None:
        raise RuntimeError("bedrock-agentcore is required to run the AgentCore runtime server.")
    app.run()
