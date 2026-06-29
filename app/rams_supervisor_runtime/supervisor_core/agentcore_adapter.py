from __future__ import annotations

from typing import Any

from .agent import run_site_briefing


def ping() -> dict[str, str]:
    return {"status": "ok", "service": "3d-rams-agentcore"}


def handle_invocation(payload: dict[str, Any] | None) -> dict[str, Any]:
    payload = payload or {}
    request = _extract_request(payload)
    run = run_site_briefing(request)
    return {
        "output": {
            "reportStatus": "review_required" if run["safety"]["allowed"] else "blocked",
            "workflowMode": _workflow_mode(run),
            "run": run,
        }
    }


def _extract_request(payload: dict[str, Any]) -> dict[str, Any]:
    input_payload = payload.get("input", payload)
    if not isinstance(input_payload, dict):
        return {"additionalRequest": str(input_payload)}

    request = dict(input_payload)
    location_text = request.pop("locationText", None)
    upstream = request.pop("upstream", None)
    if location_text and not request.get("siteName"):
        request["siteName"] = str(location_text)
    if upstream:
        request["agentcoreUpstream"] = upstream
    return request


def _workflow_mode(run: dict[str, Any]) -> str:
    fixture_mode = run.get("runtime", {}).get("fixturePackMode")
    if fixture_mode == "cached-public-fixture":
        return "cached_public_fixture"
    if fixture_mode == "synthetic-default":
        return "synthetic_fixture"
    return str(fixture_mode or "unknown")
