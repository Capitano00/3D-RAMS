from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient


REPO_ROOT = Path(__file__).resolve().parents[1]
SIDECAR_MAIN = REPO_ROOT / "agentcore-prototype" / "app" / "fieldbrief_agent" / "main.py"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

os.environ.setdefault("ENABLE_BEDROCK", "false")
os.environ.setdefault("DURABLE_RUN_PROCESS_INLINE", "true")
os.environ.pop("APP_ACCESS_TOKEN_HASH", None)

from backend.app.run_store import clear_all_runs_for_tests  # noqa: E402


def _fake_nearest_postcode_response() -> Mock:
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "status": 200,
        "result": [
            {
                "postcode": "BN2 0QU",
                "outcode": "BN2",
                "latitude": 50.8253,
                "longitude": -0.1251,
                "admin_district": "Brighton and Hove",
                "admin_ward": "Queen's Park",
                "parish": "Brighton and Hove, unparished area",
                "region": "South East",
                "country": "England",
            }
        ],
    }
    return response


def _load_sidecar_module() -> Any:
    spec = importlib.util.spec_from_file_location("fieldbrief_agent_sidecar_smoke", SIDECAR_MAIN)
    if not spec or not spec.loader:
        raise RuntimeError(f"Unable to load sidecar module from {SIDECAR_MAIN}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    clear_all_runs_for_tests()
    sidecar = _load_sidecar_module()

    help_response = sidecar.invoke({"message": "How does this work?", "useBedrock": False})
    _assert(help_response["action"] == "answered_from_memory", "Help prompt should not start a run.")
    _assert(help_response["route"] == "help", "Help prompt should route to help.")
    _assert(help_response["sidecar"]["agentCoreRuntimeLive"] is False, "Sidecar must not claim live AgentCore Runtime.")

    unsafe = sidecar.invoke({"message": "Please certify RAMS and approve work today.", "useBedrock": False})
    _assert(unsafe["action"] == "started_run", "Unsafe prompt should enter guarded run path.")
    _assert(unsafe["run"]["status"] == "completed", "Unsafe prompt should complete at the safety gate.")
    _assert(unsafe["run"]["safetyResult"]["level"] == "blocked", "Unsafe prompt should be blocked.")
    _assert(unsafe["run"]["modelCallsUsed"] == 0, "Unsafe prompt must not use model calls.")

    with patch("backend.app.location_resolver.httpx.get", return_value=_fake_nearest_postcode_response()):
        coordinate = sidecar.invoke(
            {
                "message": "I want to visit 50.825351, -0.125125 tomorrow for a roof survey.",
                "useBedrock": False,
            }
        )
    _assert(coordinate["run"]["status"] == "waiting_for_location_confirmation", "Coordinate prompt should wait for confirmation.")
    _assert(coordinate["run"]["toolResults"] == [], "Review tools must not run before location confirmation.")
    candidates = coordinate["run"]["result"]["locationCandidates"]
    _assert(candidates and candidates[0]["name"] == "Coordinate 50.825351, -0.125125", "Coordinate label should be stable.")
    confirmed_coordinate = sidecar.invoke(
        {
            "action": "confirm_location",
            "runId": coordinate["run"]["runId"],
            "candidateId": candidates[0]["candidateId"],
            "useBedrock": False,
        }
    )
    _assert(confirmed_coordinate["action"] == "confirmed_location", "Confirm action should run through the sidecar.")
    _assert(confirmed_coordinate["run"]["status"] == "completed", "Confirmed coordinate workflow should complete.")
    _assert(confirmed_coordinate["run"]["finalUiState"]["safety"]["level"] == "review_required", "Confirmed workflow should keep human-review safety.")
    _assert(len(confirmed_coordinate["run"]["toolResults"]) >= 5, "Confirmed workflow should run review tools.")
    _assert(confirmed_coordinate["run"]["result"]["briefing"], "Confirmed workflow should include a review pack.")
    _assert(confirmed_coordinate["run"]["result"]["evidence"] is not None, "Confirmed workflow should include evidence array.")
    _assert(confirmed_coordinate["run"]["result"]["trace"], "Confirmed workflow should include trace.")
    _assert(confirmed_coordinate["run"]["result"]["runtime"]["modelCallCount"] == confirmed_coordinate["run"]["modelCallsUsed"], "Model-call metadata should match run contract.")

    first = sidecar.invoke(
        {
            "message": "I want to visit Greenacre Solar Farm tomorrow for a survey. Please prepare a pre-visit RAMS-style review pack.",
            "useBedrock": False,
        }
    )
    chat_confirmation = sidecar.invoke(
        {
            "sessionId": first["run"]["sessionId"],
            "message": "yes",
            "useBedrock": False,
        }
    )
    _assert(chat_confirmation["route"] == "confirm_by_chat", "Chat-only confirmation should not run tools.")
    _assert(first["run"]["toolResults"] == [], "Chat-only confirmation must leave review tools stopped.")
    follow_up = sidecar.invoke(
        {
            "sessionId": first["run"]["sessionId"],
            "message": "What do you mean",
            "useBedrock": False,
        }
    )
    _assert(follow_up["action"] == "answered_from_memory", "Follow-up should answer from memory.")
    _assert(follow_up["route"] == "follow_up", "Follow-up should route as follow_up.")
    _assert("review pack for What do you mean" not in follow_up["assistantMessage"], "Follow-up must not become a fake site run.")

    client = TestClient(sidecar.app)
    ping = client.get("/ping")
    _assert(ping.status_code == 200, "/ping should be healthy.")
    _assert(ping.json()["status"] == "Healthy", "/ping should return AgentCore health status.")

    invocation = client.post("/invocations", json={"prompt": "How does this work?", "useBedrock": False})
    _assert(invocation.status_code == 200, "/invocations should accept AgentCore prompt payload.")
    payload = invocation.json()
    _assert(payload["status"] == "success", "/invocations should return success status.")
    _assert(payload["details"]["route"] == "help", "/invocations should preserve route details.")
    _assert(payload["details"]["sidecar"]["trafficPolicy"] == "parallel-sidecar-no-teammate-traffic", "Traffic policy should stay sidecar-only.")

    print("AgentCore sidecar smoke passed.")


if __name__ == "__main__":
    main()
