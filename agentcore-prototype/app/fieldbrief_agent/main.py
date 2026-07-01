from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.config import RuntimeConfig  # noqa: E402
from backend.app.conversation_router import handle_conversation_message  # noqa: E402
from backend.app.durable_runner import confirm_location_for_run  # noqa: E402
from backend.app.session_store import add_conversation_turn, create_session, update_working_memory  # noqa: E402


app = FastAPI(title="3D-RAMS AgentCore Sidecar Prototype", version="0.1.0")


def invoke(payload: dict[str, Any]) -> dict[str, Any]:
    """AgentCore prototype invoke function.

    This function intentionally mirrors the hosted conversation contract while
    keeping the current MVP's guards and app-layer memory intact. It is a
    sidecar prototype entrypoint, not the active hosted API path.
    """
    normalized = _normalize_payload(payload)
    os.environ.setdefault("DURABLE_RUN_PROCESS_INLINE", "true")
    use_bedrock = _payload_bool(normalized, "useBedrock", default=False)
    config = RuntimeConfig.from_env(request_bedrock=use_bedrock)
    if _is_confirm_location_action(normalized):
        return _confirm_location(normalized, config, use_bedrock=use_bedrock)
    session_id = normalized.get("sessionId")
    if not session_id:
        session = create_session(
            tester_alias=normalized.get("testerAlias") or "agentcore-prototype",
            access_label="agentcore-prototype",
            config=config,
        )
        session_id = session["sessionId"]
    result = handle_conversation_message(
        session_id=session_id,
        message=str(normalized.get("message") or "What can 3D-RAMS do?"),
        uploaded_file_ids=list(normalized.get("uploadedFileIds") or []),
        use_bedrock=use_bedrock,
        config=config,
    )
    result.setdefault("sessionId", session_id)
    result["sidecar"] = _sidecar_contract(use_bedrock=use_bedrock)
    return result


@app.post("/invocations")
def invocations(payload: dict[str, Any]) -> dict[str, Any]:
    """AgentCore HTTP protocol entrypoint for non-streaming JSON invocations."""
    return to_agentcore_response(invoke(payload))


@app.get("/ping")
def ping() -> dict[str, Any]:
    """AgentCore HTTP health endpoint."""
    return {
        "status": "Healthy",
        "time_of_last_update": int(time.time()),
        "service": "3d-rams-agentcore-sidecar-prototype",
    }


def to_agentcore_response(result: dict[str, Any]) -> dict[str, Any]:
    """Return the non-streaming JSON shape expected by the AgentCore HTTP contract."""
    return {
        "response": _assistant_response_text(result),
        "status": "success",
        "details": result,
    }


def _normalize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload or {})
    if "message" not in normalized and normalized.get("prompt"):
        normalized["message"] = normalized["prompt"]
    if "sessionId" not in normalized and normalized.get("session_id"):
        normalized["sessionId"] = normalized["session_id"]
    if "runId" not in normalized and normalized.get("run_id"):
        normalized["runId"] = normalized["run_id"]
    if "candidateId" not in normalized and normalized.get("candidate_id"):
        normalized["candidateId"] = normalized["candidate_id"]
    if "uploadedFileIds" not in normalized and normalized.get("uploaded_file_ids"):
        normalized["uploadedFileIds"] = normalized["uploaded_file_ids"]
    return normalized


def _payload_bool(payload: dict[str, Any], key: str, *, default: bool) -> bool:
    value = payload.get(key, default)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def _assistant_response_text(result: dict[str, Any]) -> str:
    if result.get("assistantMessage"):
        return str(result["assistantMessage"])
    run = result.get("run") or {}
    run_result = run.get("result") or {}
    if run_result.get("assistantMessage"):
        return str(run_result["assistantMessage"])
    status = run.get("status")
    current_step = run.get("currentStep")
    if status:
        return f"Run {status}: {current_step}."
    return "3D-RAMS AgentCore sidecar processed the request."


def _is_confirm_location_action(payload: dict[str, Any]) -> bool:
    action = str(payload.get("action") or payload.get("operation") or "").strip().lower().replace("-", "_")
    return action in {"confirm_location", "confirm_location_candidate"}


def _confirm_location(payload: dict[str, Any], config: RuntimeConfig, *, use_bedrock: bool) -> dict[str, Any]:
    run_id = str(payload.get("runId") or "").strip()
    candidate_id = str(payload.get("candidateId") or "").strip()
    if not run_id:
        raise ValueError("confirm_location requires runId.")
    if not candidate_id:
        raise ValueError("confirm_location requires candidateId.")

    run = confirm_location_for_run(run_id, candidate_id, config)
    session_id = run.get("sessionId")
    assistant_text = _assistant_response_text({"run": run})
    if session_id:
        add_conversation_turn(
            session_id,
            role="assistant",
            text=assistant_text,
            metadata={"route": "confirm_location", "runId": run_id, "runStatus": run.get("status")},
            config=config,
        )
        update_working_memory(
            session_id,
            config,
            activeRunId=run_id,
            latestRunStatus=run.get("status"),
            pendingUserAction=None if run.get("status") == "completed" else "wait_for_agent_run",
            confirmedLocation=run.get("confirmedLocation") or run.get("locationResolution", {}).get("confirmedLocation"),
            latestReviewSummary={
                "runId": run_id,
                "status": run.get("status"),
                "headline": run.get("result", {}).get("briefing", {}).get("headline"),
            },
        )
    return {
        "action": "confirmed_location",
        "route": "confirm_location",
        "sessionId": session_id,
        "assistantMessage": assistant_text,
        "run": run,
        "runtime": run.get("result", {}).get("runtime") or run.get("runtime") or {},
        "sidecar": _sidecar_contract(use_bedrock=use_bedrock),
    }


def _sidecar_contract(*, use_bedrock: bool) -> dict[str, Any]:
    return {
        "prototype": True,
        "trafficPolicy": "parallel-sidecar-no-teammate-traffic",
        "httpProtocol": "AgentCore /invocations JSON, /ping health",
        "activeHostedRuntime": "api-gateway-lambda-fastapi",
        "agentCoreRuntimeLive": False,
        "agentCoreMemory": "disabled",
        "memoryMode": "bounded-session-working-memory",
        "guardsFirst": True,
        "locationConfirmationBeforeTools": True,
        "confirmLocationAction": "confirm_location",
        "bedrockRequested": use_bedrock,
    }


def main() -> None:
    """Local stdin/stdout harness for prototype smoke checks."""
    raw = sys.stdin.read().strip()
    payload = json.loads(raw) if raw else {}
    print(json.dumps(invoke(payload), indent=2))


if __name__ == "__main__":
    os.environ.setdefault("ENABLE_BEDROCK", "false")
    main()
