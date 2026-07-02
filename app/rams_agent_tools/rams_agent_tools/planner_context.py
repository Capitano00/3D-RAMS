from __future__ import annotations

from typing import Any


PLANNER_CONTEXT_SCHEMA_VERSION = "3d-rams.hosted-planner-context.v1"

_FORBIDDEN_KEYS = {
    "accesscode",
    "accesstoken",
    "apihandle",
    "bearertoken",
    "conversationhistory",
    "conversationid",
    "hiddenreasoning",
    "messages",
    "privatematerials",
    "privatenotes",
    "rawcontent",
    "rawconversationhistory",
    "rawprompt",
    "rawsessioncontext",
    "rawturntext",
    "refreshtoken",
    "retrievalurl",
    "sessionid",
    "signedurl",
    "token",
}


def bounded_planner_context(request: dict[str, Any]) -> dict[str, Any]:
    location_candidate = _dict(request.get("locationCandidate"))
    location_confirmation = _dict(request.get("locationConfirmation"))
    location = {
        "label": _text(request.get("siteName") or location_candidate.get("label")),
        "confirmationStatus": _text(location_confirmation.get("status")),
        "source": _text(location_candidate.get("source")),
        "dataMode": _text(location_candidate.get("dataMode")),
        "confidence": location_candidate.get("confidence"),
    }
    context = {
        "schemaVersion": PLANNER_CONTEXT_SCHEMA_VERSION,
        "caseId": _text(request.get("caseId")),
        "location": _drop_empty(location),
        "areaScope": _dict(request.get("areaScope")),
        "userGoal": _text(request.get("goal")),
        "fixturePack": _text(request.get("fixturePack")),
        "dataMode": _text(location_candidate.get("dataMode")) or _fixture_data_mode(request),
        "materialSummary": _material_summary(request.get("materials")),
        "runtimeSummary": _runtime_summary(request),
    }
    return _drop_empty(context)


def public_upstream_context(value: Any) -> dict[str, Any]:
    upstream = _dict(value)
    safe = {
        "source": _text(upstream.get("source")),
        "adapterVersion": _text(upstream.get("adapterVersion")),
        "caseId": _text(upstream.get("caseId")),
        "entryAgentId": _text(upstream.get("entryAgentId")),
        "confirmedByUser": upstream.get("confirmedByUser") if isinstance(upstream.get("confirmedByUser"), bool) else None,
        "areaScope": _dict(upstream.get("areaScope")),
        "locationConfidence": upstream.get("locationConfidence"),
        "materialCount": _int_or_none(upstream.get("materialCount")),
    }
    if isinstance(upstream.get("reportAccess"), dict):
        safe["reportAccess"] = {"status": "redacted", "reason": "stored_as_hashed_report_access_binding"}
    return _drop_empty(safe)


def redact_for_public_output(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned = {}
        for key, item in value.items():
            if _forbidden_key(key):
                continue
            if key in {"reportAccess", "reportAccessContext", "accessContext"}:
                cleaned[key] = {
                    "status": "redacted",
                    "reason": "stored_as_hashed_report_access_binding",
                }
                continue
            cleaned[key] = redact_for_public_output(item)
        return cleaned
    if isinstance(value, list):
        return [redact_for_public_output(item) for item in value]
    return value


def _material_summary(value: Any) -> dict[str, Any]:
    materials = [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []
    statuses = []
    types = []
    source_systems = []
    for item in materials:
        access = _dict(item.get("access"))
        status = _text(access.get("status"))
        material_type = _text(item.get("type"))
        source_system = _text(item.get("sourceSystem"))
        if status and status not in statuses:
            statuses.append(status)
        if material_type and material_type not in types:
            types.append(material_type)
        if source_system and source_system not in source_systems:
            source_systems.append(source_system)
    return _drop_empty(
        {
            "count": len(materials),
            "statuses": statuses,
            "types": types,
            "sourceSystems": source_systems,
        }
    )


def _runtime_summary(request: dict[str, Any]) -> dict[str, Any]:
    runtime = _dict(request.get("runtimeObservability") or request.get("dogfoodSummary"))
    allowed = {
        "schemaVersion",
        "modelPath",
        "modelProvider",
        "plannerMode",
        "activeAgentMode",
        "fallbackReason",
        "fixturePackMode",
    }
    return _drop_empty({key: runtime[key] for key in allowed if key in runtime})


def _fixture_data_mode(request: dict[str, Any]) -> str | None:
    if request.get("fixturePack"):
        return "cached-public-fixture"
    return None


def _forbidden_key(key: Any) -> bool:
    normalized = "".join(ch for ch in str(key).lower() if ch.isalnum())
    return normalized in _FORBIDDEN_KEYS


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _drop_empty(value: dict[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if item not in (None, "", [], {})}
