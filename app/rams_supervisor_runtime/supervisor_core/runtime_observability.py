from __future__ import annotations

from typing import Any


RUNTIME_OBSERVABILITY_SCHEMA_VERSION = "3d-rams.runtime-observability.v1"


def runtime_observability(runtime: dict[str, Any], run: dict[str, Any] | None = None) -> dict[str, Any]:
    run = run or {}
    token_usage = run.get("tokenUsage")
    model_calls = run.get("modelCalls") if isinstance(run.get("modelCalls"), list) else []
    latency_ms = _latency_ms(model_calls)
    harness_contract = runtime.get("harnessContract") if isinstance(runtime.get("harnessContract"), dict) else {}
    failure_summaries = runtime.get("executionFailureSummaries")
    summary = {
        "schemaVersion": RUNTIME_OBSERVABILITY_SCHEMA_VERSION,
        "modelPath": _model_path(runtime),
        "modelProvider": runtime.get("modelProvider"),
        "modelId": runtime.get("modelId"),
        "awsRegion": runtime.get("awsRegion"),
        "modelCallCount": int(runtime.get("modelCallCount") or 0),
        "tokenUsage": token_usage if isinstance(token_usage, dict) else None,
        "latencyMs": latency_ms,
        "bedrockRequested": bool(runtime.get("bedrockRequested")),
        "bedrockEnabled": bool(runtime.get("bedrockEnabled")),
        "bedrockUsed": bool(runtime.get("bedrockUsed")),
        "plannerMode": runtime.get("plannerMode"),
        "activeAgentMode": runtime.get("activeAgentMode"),
        "fallbackReason": runtime.get("fallbackReason"),
        "harnessOutputSchemaVersion": runtime.get("harnessOutputSchemaVersion"),
        "harnessContractStatus": "compliant" if harness_contract.get("contractCompliant", True) else "fallback",
        "executionFailureSummaries": failure_summaries if isinstance(failure_summaries, list) and failure_summaries else None,
    }
    return {key: value for key, value in summary.items() if value is not None}


def _model_path(runtime: dict[str, Any]) -> str:
    if runtime.get("modelProvider") == "openai-compatible" and runtime.get("bedrockEnabled"):
        return "openai-compatible"
    if runtime.get("bedrockUsed"):
        return "bedrock"
    if runtime.get("plannerMode") == "fallback" or runtime.get("briefingMode") == "fallback":
        return "fallback"
    return str(runtime.get("activeAgentMode") or runtime.get("plannerMode") or runtime.get("briefingMode") or "unknown")


def _latency_ms(model_calls: list[Any]) -> int | None:
    values = []
    for call in model_calls:
        if not isinstance(call, dict):
            continue
        value = call.get("latencyMs")
        if isinstance(value, (int, float)):
            values.append(int(value))
    return sum(values) if values else None
