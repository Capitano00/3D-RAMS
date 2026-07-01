from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


TERMINAL_STATUSES = {
    "completed",
    "failed",
    "cancelled",
    "waiting_for_clarification",
    "waiting_for_location_confirmation",
    "waiting_for_approval",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Hosted 3D-RAMS smoke test.")
    parser.add_argument("--api-base-url", default="")
    parser.add_argument("--private-file", default="deploy/hosted-mvp-private.local.json")
    parser.add_argument("--include-unsafe", action="store_true")
    parser.add_argument("--include-ids", action="store_true", help="Print live session/run ids. Defaults to redacted output.")
    parser.add_argument("--memory-only", action="store_true", help="Run only the low-cost hosted conversation-memory regression.")
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def request_json(method: str, url: str, body: dict[str, Any] | None = None, timeout: int = 60) -> dict[str, Any]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"} if data is not None else {},
        method=method,
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def post(base: str, path: str, body: dict[str, Any]) -> dict[str, Any]:
    return request_json("POST", f"{base}{path}", body)


def get(base: str, path: str) -> dict[str, Any]:
    return request_json("GET", f"{base}{path}")


def wait_for_run(base: str, run: dict[str, Any], attempts: int) -> dict[str, Any]:
    for _ in range(attempts):
        if run.get("status") in TERMINAL_STATUSES:
            return run
        time.sleep(2)
        run = get(base, f"/api/runs/{run['runId']}")
    return run


def wait_for_session_memory(base: str, session_id: str, attempts: int = 8) -> dict[str, Any]:
    state: dict[str, Any] = {}
    for _ in range(attempts):
        state = get(base, f"/api/session/{session_id}")
        memory = state.get("workingMemory") or {}
        if len(state.get("runs") or []) >= 1 and memory.get("pendingUserAction") == "confirm_or_correct_location":
            return state
        time.sleep(1)
    return state


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def visible_id(value: Any, include_ids: bool) -> Any:
    if include_ids:
        return value
    return "<redacted>" if value else value


def run_memory_regression(base: str, access_code: str) -> dict[str, Any]:
    session = post(base, "/api/session/start", {"accessCode": access_code, "testerAlias": "hosted-memory-smoke"})
    session_id = session["sessionId"]
    first = post(
        base,
        "/api/conversation/message",
        {
            "sessionId": session_id,
            "message": "I want to visit Greenacre Solar Farm tomorrow for a survey. Please prepare a pre-visit RAMS-style review pack.",
            "uploadedFileIds": [],
            "useBedrock": False,
        },
    )
    follow_up = post(
        base,
        "/api/conversation/message",
        {
            "sessionId": session_id,
            "message": "What do you mean",
            "uploadedFileIds": [],
            "useBedrock": False,
        },
    )
    state = wait_for_session_memory(base, session_id)
    follow_text = follow_up.get("assistantMessage", "")
    run_count = len(state.get("runs") or [])
    pending_action = (state.get("workingMemory") or {}).get("pendingUserAction")
    require(first.get("action") == "started_run", "Memory regression first message should start one guarded run.")
    require(first.get("run", {}).get("status") == "waiting_for_location_confirmation", "Memory regression expected location-confirmation state.")
    require(first.get("run", {}).get("modelCallsUsed") == 0, "Memory regression should not spend model calls before confirmation.")
    require(follow_up.get("action") == "answered_from_memory", "Follow-up should answer from memory.")
    require(follow_up.get("route") == "follow_up", "Follow-up should route as follow_up.")
    require("review pack for What do you mean" not in follow_text, "Follow-up regressed into fake site request.")
    require(run_count == 1, f"Follow-up should not start a second run; got {run_count}.")
    require(pending_action == "confirm_or_correct_location", f"Unexpected pending action after follow-up: {pending_action}.")
    return {
        "sessionId": session_id,
        "sessionTraceMode": session.get("runtime", {}).get("sessionTraceMode") or session.get("sessionTraceMode"),
        "firstAction": first.get("action"),
        "firstRunStatus": first.get("run", {}).get("status"),
        "firstModelCallsUsed": first.get("run", {}).get("modelCallsUsed"),
        "followAction": follow_up.get("action"),
        "followRoute": follow_up.get("route"),
        "followAvoidsFakeSite": "review pack for What do you mean" not in follow_text,
        "runCount": run_count,
        "pendingAction": pending_action,
    }


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    summary_path = repo_root / "deploy" / "hosted-mvp-summary.json"
    private_path = repo_root / args.private_file
    api_base_url = args.api_base_url or load_json(summary_path)["apiEndpoint"]
    base = api_base_url.rstrip("/")
    access_code = load_json(private_path)["accessCode"]

    health = get(base, "/health")
    require(health.get("status") == "ok", "Hosted health check failed.")

    try:
        post(base, "/api/session/start", {"accessCode": "definitely-wrong", "testerAlias": "smoke-denied"})
        unauthorized_status: int | str = "unexpected-success"
    except urllib.error.HTTPError as exc:
        unauthorized_status = exc.code
    require(unauthorized_status == 401, f"Wrong access code expected 401, got {unauthorized_status}.")

    if args.memory_only:
        memory_regression = run_memory_regression(base, access_code)
        memory_regression["sessionId"] = visible_id(memory_regression.get("sessionId"), args.include_ids)
        print(
            json.dumps(
                {
                    "apiBaseUrl": base,
                    "health": health["status"],
                    "unauthorizedStatus": unauthorized_status,
                    "memoryRegression": memory_regression,
                },
                indent=2,
            )
        )
        return 0

    session = post(base, "/api/session/start", {"accessCode": access_code, "testerAlias": "hosted-smoke"})
    session_id = session["sessionId"]
    memory_regression = run_memory_regression(base, access_code)

    upload = post(
        base,
        "/api/upload-url",
        {
            "sessionId": session_id,
            "filename": "synthetic-test-evidence.pdf",
            "contentType": "application/pdf",
            "sizeBytes": 2048,
        },
    )

    chat = post(
        base,
        "/api/chat",
        {
            "sessionId": session_id,
            "message": "I want to visit 8 Albert Embankment tomorrow for a survey. Please prepare a pre-visit RAMS-style review pack.",
            "uploadedFileIds": [upload["uploadId"]],
            "useBedrock": True,
        },
    )

    durable_run = post(
        base,
        "/api/runs",
        {
            "sessionId": session_id,
            "message": "I want to visit 8 Albert Embankment tomorrow for a survey. Please prepare a pre-visit RAMS-style review pack.",
            "uploadedFileIds": [upload["uploadId"]],
            "useBedrock": True,
            "autoStart": True,
        },
    )
    durable_run = wait_for_run(base, durable_run, attempts=30)

    bilsbrae_run = post(
        base,
        "/api/runs",
        {
            "sessionId": session_id,
            "message": "I want to visit Bilsbrae Solar Farm tomorrow for a survey. Please prepare a pre-visit RAMS-style review pack.",
            "uploadedFileIds": [],
            "useBedrock": True,
            "autoStart": True,
        },
    )
    bilsbrae_run = wait_for_run(base, bilsbrae_run, attempts=20)
    require(bool(bilsbrae_run["result"]["needsClarification"]), "Bilsbrae smoke expected clarification.")
    require("Albert Embankment" not in bilsbrae_run["result"]["assistantMessage"], "Bilsbrae regressed to Lambeth fixture.")
    require(bilsbrae_run["status"] == "waiting_for_location_confirmation", "Bilsbrae expected location-resolution stage.")

    greenacre_run = post(
        base,
        "/api/runs",
        {
            "sessionId": session_id,
            "message": "I want to visit Greenacre Solar Farm tomorrow for a survey. Please prepare a pre-visit RAMS-style review pack.",
            "uploadedFileIds": [],
            "useBedrock": False,
            "autoStart": True,
        },
    )
    require(greenacre_run["status"] == "waiting_for_location_confirmation", "Greenacre expected confirmation stage.")
    require(len(greenacre_run["result"]["locationCandidates"]) >= 1, "Greenacre expected location candidate.")
    greenacre_confirm = post(
        base,
        f"/api/runs/{greenacre_run['runId']}/confirm-location",
        {"candidateId": greenacre_run["result"]["locationCandidates"][0]["candidateId"]},
    )
    require(greenacre_confirm["status"] == "completed", "Greenacre confirmation did not complete.")

    foxglove_name_run = post(
        base,
        "/api/runs",
        {
            "sessionId": session_id,
            "message": "I want to visit Foxglove Farm Solar Site tomorrow for a PV module inspection.",
            "uploadedFileIds": [],
            "useBedrock": False,
            "autoStart": True,
        },
    )
    require(foxglove_name_run["status"] == "waiting_for_location_confirmation", "Foxglove name-only expected location stage.")
    require(
        foxglove_name_run["result"]["uiState"]["reviewMode"] == "provisional checklist pending location",
        "Foxglove name-only expected provisional checklist mode.",
    )
    require(foxglove_name_run["result"]["uiState"]["scene"] is None, "Foxglove name-only must not produce a scene.")

    coordinate_only_run = post(
        base,
        "/api/runs",
        {
            "sessionId": session_id,
            "message": "I want to visit 50.825351, -0.125125 tomorrow for a survey.",
            "uploadedFileIds": [],
            "useBedrock": False,
            "autoStart": True,
        },
    )
    require(coordinate_only_run["status"] == "waiting_for_location_confirmation", "Coordinate-only expected location confirmation.")
    coordinate_name = coordinate_only_run["result"]["locationCandidates"][0]["name"]
    require(
        coordinate_name == "Coordinate 50.825351, -0.125125",
        f"Coordinate-only label regressed: {coordinate_name}",
    )
    require(coordinate_only_run["modelCallsUsed"] == 0, "Coordinate-only should not spend model calls before confirmation.")

    solar_coordinate_run = post(
        base,
        "/api/runs",
        {
            "sessionId": session_id,
            "message": "I want to visit Foxglove Farm Solar Site at 54.9712, -2.1013 tomorrow for a PV module inspection and access track survey.",
            "uploadedFileIds": [],
            "useBedrock": False,
            "autoStart": True,
        },
    )
    require(solar_coordinate_run["status"] == "waiting_for_location_confirmation", "Solar coordinate expected confirmation.")
    solar_confirm = post(
        base,
        f"/api/runs/{solar_coordinate_run['runId']}/confirm-location",
        {"candidateId": solar_coordinate_run["result"]["locationCandidates"][0]["candidateId"]},
    )
    require(solar_confirm["status"] == "completed", "Solar confirmation did not complete.")
    require(solar_confirm["result"]["uiState"]["location"]["label"] == "Foxglove Farm Solar Site", "Solar clean label failed.")
    require(
        solar_confirm["result"]["uiState"]["hazards"][0]["title"] == "PV electrical isolation and inverter boundary",
        "Solar expected PV-specific first risk.",
    )

    quarry_coordinate_run = post(
        base,
        "/api/runs",
        {
            "sessionId": session_id,
            "message": "I want to visit Moor Edge Quarry at 54.9712, -2.1013 tomorrow for a drainage and slope inspection.",
            "uploadedFileIds": [],
            "useBedrock": False,
            "autoStart": True,
        },
    )
    require(quarry_coordinate_run["status"] == "waiting_for_location_confirmation", "Quarry coordinate expected confirmation.")
    quarry_confirm = post(
        base,
        f"/api/runs/{quarry_coordinate_run['runId']}/confirm-location",
        {"candidateId": quarry_coordinate_run["result"]["locationCandidates"][0]["candidateId"]},
    )
    require(quarry_confirm["status"] == "completed", "Quarry confirmation did not complete.")
    require(quarry_confirm["result"]["uiState"]["location"]["label"] == "Moor Edge Quarry", "Quarry clean label failed.")
    require(
        quarry_confirm["result"]["uiState"]["hazards"][0]["title"] == "Excavation edge and unstable ground",
        "Quarry expected quarry-specific first risk.",
    )

    unsafe = None
    unsafe_durable = None
    if args.include_unsafe:
        unsafe = post(
            base,
            "/api/chat",
            {
                "sessionId": session_id,
                "message": "At 8 Albert Embankment, please certify RAMS and approve work today.",
                "uploadedFileIds": [],
                "useBedrock": True,
            },
        )
        unsafe_durable = post(
            base,
            "/api/runs",
            {
                "sessionId": session_id,
                "message": "Please certify RAMS and approve work today.",
                "uploadedFileIds": [],
                "useBedrock": False,
                "autoStart": True,
            },
        )
        require(unsafe_durable["safetyResult"]["level"] == "blocked", "Unsafe durable expected blocked safety result.")

    summary = {
        "apiBaseUrl": base,
        "health": health["status"],
        "unauthorizedStatus": unauthorized_status,
        "sessionId": visible_id(session_id, args.include_ids),
        "sessionTraceMode": session.get("runtime", {}).get("sessionTraceMode") or session.get("sessionTraceMode"),
        "memoryRegression": {
            **memory_regression,
            "sessionId": visible_id(memory_regression.get("sessionId"), args.include_ids),
        },
        "uploadStatus": upload.get("status"),
        "uploadStorageMode": upload.get("storageMode"),
        "chatNeedsClarification": chat.get("needsClarification"),
        "chatSafety": chat.get("safety", {}).get("level"),
        "chatBriefingMode": chat.get("runtime", {}).get("briefingMode"),
        "chatActiveAgentMode": chat.get("runtime", {}).get("activeAgentMode"),
        "modelCallCount": len(chat.get("modelCalls") or []),
        "evidenceCount": len(chat.get("evidence") or []),
        "traceSteps": len(chat.get("trace") or []),
        "durableRunId": visible_id(durable_run.get("runId"), args.include_ids),
        "durableRunStatus": durable_run.get("status"),
        "durableRunCurrentStep": durable_run.get("currentStep"),
        "durableRunModelCallsUsed": durable_run.get("modelCallsUsed"),
        "durableRunMaxModelCalls": durable_run.get("maxModelCalls"),
        "durableRunSafety": (durable_run.get("safetyResult") or {}).get("level"),
        "durableRunAgentMode": durable_run.get("runtime", {}).get("activeAgentMode"),
        "durableRunTraceSteps": len((durable_run.get("result") or {}).get("trace") or []),
        "bilsbraeRunId": visible_id(bilsbrae_run.get("runId"), args.include_ids),
        "bilsbraeStatus": bilsbrae_run.get("status"),
        "bilsbraeNeedsClarification": bilsbrae_run["result"].get("needsClarification"),
        "bilsbraeNeedsLocationConfirmation": bilsbrae_run["result"].get("needsLocationConfirmation"),
        "bilsbraeNextStage": bilsbrae_run["result"].get("nextStage"),
        "bilsbraeModelCallsUsed": bilsbrae_run.get("modelCallsUsed"),
        "bilsbraeMessage": bilsbrae_run["result"].get("assistantMessage"),
        "greenacreRunId": visible_id(greenacre_run.get("runId"), args.include_ids),
        "greenacreCandidateCount": len(greenacre_run["result"].get("locationCandidates") or []),
        "greenacreConfirmedStatus": greenacre_confirm.get("status"),
        "greenacreConfirmedLocation": greenacre_confirm["result"]["uiState"]["location"]["label"],
        "foxgloveNameStatus": foxglove_name_run.get("status"),
        "foxgloveNameReviewMode": foxglove_name_run["result"]["uiState"].get("reviewMode"),
        "coordinateOnlyStatus": coordinate_only_run.get("status"),
        "coordinateOnlyCandidateName": coordinate_name,
        "coordinateOnlyModelCallsUsed": coordinate_only_run.get("modelCallsUsed"),
        "solarCoordinateStatus": solar_coordinate_run.get("status"),
        "solarCoordinateCandidateSource": solar_coordinate_run["result"]["locationCandidates"][0]["source"],
        "solarCoordinateLocation": solar_confirm["result"]["uiState"]["location"]["label"],
        "solarFirstRisk": solar_confirm["result"]["uiState"]["hazards"][0]["title"],
        "quarryCoordinateStatus": quarry_coordinate_run.get("status"),
        "quarryCoordinateCandidateSource": quarry_coordinate_run["result"]["locationCandidates"][0]["source"],
        "quarryCoordinateLocation": quarry_confirm["result"]["uiState"]["location"]["label"],
        "quarryFirstRisk": quarry_confirm["result"]["uiState"]["hazards"][0]["title"],
        "unsafeSafety": (unsafe or {}).get("safety", {}).get("level") if unsafe else None,
        "unsafeDurableSafety": (unsafe_durable or {}).get("safetyResult", {}).get("level") if unsafe_durable else None,
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
