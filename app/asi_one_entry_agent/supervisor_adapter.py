from __future__ import annotations

import os
from typing import Any


ADAPTER_VERSION = "agentverse-agentcore-adapter-v0"


class AdapterValidationError(ValueError):
    """Raised when an entry-agent payload is not ready for AgentCore launch."""


def build_agentcore_invocation(entry_payload: dict[str, Any]) -> dict[str, Any]:
    payload = _require_mapping(entry_payload, "entry_payload")
    intake = _require_mapping(payload.get("intake"), "intake")
    runtime_options = payload.get("runtimeOptions") or {}
    if not isinstance(runtime_options, dict):
        raise AdapterValidationError("runtimeOptions must be an object when provided.")

    confirmed = payload.get("confirmedByUser")
    if confirmed is not True:
        raise AdapterValidationError("confirmedByUser must be true before invoking AgentCore.")

    case_id = _optional_text(payload.get("caseId"))
    if not case_id:
        raise AdapterValidationError("caseId is required before invoking AgentCore.")

    location_text = _optional_text(intake.get("locationText"))
    location_candidate = intake.get("locationCandidate") or {}
    if location_candidate and not isinstance(location_candidate, dict):
        raise AdapterValidationError("intake.locationCandidate must be an object when provided.")

    has_coordinate = location_candidate.get("lat") is not None and location_candidate.get("lng") is not None
    if not location_text and not has_coordinate:
        raise AdapterValidationError("intake requires locationText or locationCandidate lat/lng.")

    area_scope = intake.get("areaScope")
    if not isinstance(area_scope, dict) or not area_scope:
        raise AdapterValidationError("intake.areaScope is required before invoking AgentCore.")

    user_goal = _optional_text(intake.get("userGoal"))
    if not user_goal:
        raise AdapterValidationError("intake.userGoal is required before invoking AgentCore.")

    materials = intake.get("materials") or []
    if not isinstance(materials, list):
        raise AdapterValidationError("intake.materials must be a list when provided.")

    input_payload: dict[str, Any] = {
        "caseId": case_id,
        "siteName": _site_name(location_text, location_candidate),
        "goal": user_goal,
        "additionalRequest": _additional_request(intake),
        "upstream": {
            "caseId": case_id,
            "source": _upstream_source(payload),
            "adapterVersion": ADAPTER_VERSION,
            "conversationId": _optional_text(payload.get("conversationId")),
            "entryAgentId": _optional_text(payload.get("entryAgentId")),
            "confirmedByUser": True,
            "areaScope": area_scope,
            "locationConfidence": location_candidate.get("confidence"),
            "materialCount": len(materials),
        },
    }

    if has_coordinate:
        input_payload["latitude"] = float(location_candidate["lat"])
        input_payload["longitude"] = float(location_candidate["lng"])
    if location_text:
        input_payload["locationText"] = location_text

    for key in ("fixturePack", "useBedrock", "includePlanningFixture", "simulateMapFailure"):
        if key in runtime_options:
            input_payload[key] = runtime_options[key]

    return {"input": input_payload}


def build_delivery_payload(
    agentcore_response: dict[str, Any],
    *,
    entry_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    response = _require_mapping(agentcore_response, "agentcore_response")
    output = _require_mapping(response.get("output"), "output")
    run = _require_mapping(output.get("run"), "output.run")
    briefing = run.get("briefing") if isinstance(run.get("briefing"), dict) else {}
    safety = run.get("safety") if isinstance(run.get("safety"), dict) else {}
    location = run.get("location") if isinstance(run.get("location"), dict) else {}
    source_entry = entry_payload or {}
    conversation_id = source_entry.get("conversationId") if isinstance(source_entry, dict) else None
    case_id = _optional_text(output.get("caseId") or run.get("caseId") or source_entry.get("caseId"))

    return {
        "caseId": case_id,
        "caseUrl": _case_url(case_id),
        "conversationId": _optional_text(conversation_id),
        "status": output.get("reportStatus") or safety.get("level") or "unknown",
        "workflowMode": output.get("workflowMode") or "unknown",
        "customerSummary": {
            "title": briefing.get("site") or location.get("label") or "3D-RAMS review pack",
            "headline": briefing.get("headline") or "Review pack generated.",
            "summary": _string_list(briefing.get("summary")),
            "priorityChecks": _string_list(briefing.get("priority_checks")),
            "safetyMessage": safety.get("message") or "Human review is required before use.",
        },
        "deepReport": {
            "kind": "agentcore_run_payload",
            "caseId": case_id,
            "casePath": f"/case/{case_id}" if case_id else None,
            "runId": run.get("runId"),
            "evidenceCount": len(run.get("evidence") or []),
            "traceCount": len(run.get("trace") or []),
            "visualizationReady": bool(run.get("scene") and run.get("architecture")),
        },
        "safetyReminder": safety.get("message") or "Human review is required before use.",
        "agentcoreOutput": output,
    }


def _require_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AdapterValidationError(f"{label} must be an object.")
    return value


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _site_name(location_text: str | None, location_candidate: dict[str, Any]) -> str:
    label = _optional_text(location_candidate.get("label"))
    if label:
        return label
    if location_text:
        return location_text
    return "Confirmed AgentVerse intake location"


def _additional_request(intake: dict[str, Any]) -> str:
    parts: list[str] = []
    user_notes = _optional_text(intake.get("userNotes"))
    if user_notes:
        parts.append(user_notes)

    for material in intake.get("materials") or []:
        if not isinstance(material, dict):
            continue
        label = _optional_text(material.get("label"))
        summary = _optional_text(material.get("summary"))
        if label and summary:
            parts.append(f"{label}: {summary}")
        elif summary:
            parts.append(summary)

    return "\n".join(parts)


def _upstream_source(payload: dict[str, Any]) -> str:
    caller = str(payload.get("caller") or "").strip().lower()
    if caller == "frontend":
        return "FRONTEND"
    if caller == "agentverse":
        return "AGENTVERSE"
    return "ASI_ONE_ENTRY_AGENT"


def _case_url(case_id: str | None) -> str | None:
    if not case_id:
        return None
    base_url = os.getenv("PUBLIC_FRONTEND_BASE_URL", "").strip().rstrip("/")
    if not base_url:
        return f"/case/{case_id}"
    return f"{base_url}/case/{case_id}"


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item is not None]
