from __future__ import annotations

import json
import re
import uuid
from typing import Any, Callable


INTAKE_SCHEMA_VERSION = "3d-rams.entry-intake.v1"
SAFETY_BOUNDARY = "This is a pre-visit review pack for human review, not certified RAMS, emergency guidance, or work approval."


class IntakeValidationError(ValueError):
    pass


def build_entry_turn(payload: dict[str, Any]) -> dict[str, Any]:
    message = _message_text(payload)
    conversation_id = str(payload.get("conversationId") or payload.get("sessionId") or "frontend-demo-session")
    return {
        "schemaVersion": INTAKE_SCHEMA_VERSION,
        "caller": str(payload.get("caller") or payload.get("source") or ("frontend" if payload.get("frontendInvoke") else "agentverse")),
        "conversationId": conversation_id,
        "entryAgentId": str(payload.get("entryAgentId") or "@3d-rams"),
        "message": message,
        "confirmedByUser": bool(payload.get("confirmedByUser") or _looks_like_confirmation(message)),
        "materials": _materials(payload),
        "runtimeOptions": _runtime_options(payload),
    }


def coordinate_intake(
    payload: dict[str, Any],
    *,
    model_json: Callable[[dict[str, Any]], dict[str, Any] | str] | None = None,
) -> dict[str, Any]:
    turn = build_entry_turn(payload)
    if isinstance(payload.get("intake"), dict):
        parsed = {
            "status": "launch_ready" if turn.get("confirmedByUser") else "confirmation_required",
            "assistantMessage": (
                "I have enough information and will launch the supervisor workflow."
                if turn.get("confirmedByUser")
                else "I have enough information. Please confirm that I should launch the supervisor run."
            ),
            "confirmation": {"summary": _confirmation_summary(payload["intake"])},
            "intake": payload["intake"],
            "caseId": payload.get("caseId"),
        }
    elif model_json:
        parsed = _coerce_model_json(model_json(_model_prompt(turn)))
    else:
        parsed = _deterministic_intake(turn)
    return validate_intake_result(parsed, turn)


def validate_intake_result(result: dict[str, Any], turn: dict[str, Any]) -> dict[str, Any]:
    status = str(result.get("status") or "").strip()
    if status not in {"clarification_required", "confirmation_required", "launch_ready"}:
        raise IntakeValidationError("intake status must be clarification_required, confirmation_required, or launch_ready.")

    response = {
        "schemaVersion": INTAKE_SCHEMA_VERSION,
        "status": status,
        "conversationId": turn["conversationId"],
        "entryAgentId": turn["entryAgentId"],
        "assistantMessage": str(result.get("assistantMessage") or _default_message(status)),
        "clarifyingQuestions": _string_list(result.get("clarifyingQuestions")),
        "confirmation": result.get("confirmation") if isinstance(result.get("confirmation"), dict) else None,
        "intake": result.get("intake") if isinstance(result.get("intake"), dict) else None,
        "caseId": None,
    }

    if status == "clarification_required":
        if not response["clarifyingQuestions"]:
            response["clarifyingQuestions"] = ["Which site and review radius should I use?"]
        response["intake"] = None
        return response

    intake = _validate_confirmed_intake(response["intake"])
    response["intake"] = intake

    if status == "confirmation_required":
        response["confirmation"] = response["confirmation"] or {"summary": _confirmation_summary(intake)}
        return response

    if turn["confirmedByUser"] is not True:
        response["status"] = "confirmation_required"
        response["confirmation"] = response["confirmation"] or {"summary": _confirmation_summary(intake)}
        response["assistantMessage"] = "I have enough information. Please confirm that I should launch the supervisor run."
        return response

    response["caseId"] = str(result.get("caseId") or generate_case_id(turn, intake))
    return response


def generate_case_id(turn: dict[str, Any], intake: dict[str, Any]) -> str:
    seed = "|".join(
        [
            str(turn.get("conversationId") or ""),
            str(intake.get("locationText") or ""),
            str(intake.get("userGoal") or ""),
            str(intake.get("areaScope", {}).get("meters") or ""),
        ]
    )
    return f"case_{uuid.uuid5(uuid.NAMESPACE_URL, seed).hex[:12]}"


def build_confirmed_entry_payload(turn: dict[str, Any], intake_result: dict[str, Any]) -> dict[str, Any]:
    if intake_result.get("status") != "launch_ready" or not intake_result.get("caseId"):
        raise IntakeValidationError("launch_ready intake with caseId is required before supervisor invocation.")
    return {
        "caseId": intake_result["caseId"],
        "conversationId": turn["conversationId"],
        "entryAgentId": turn["entryAgentId"],
        "caller": turn["caller"],
        "confirmedByUser": True,
        "intake": intake_result["intake"],
        "runtimeOptions": turn["runtimeOptions"],
    }


def _model_prompt(turn: dict[str, Any]) -> dict[str, Any]:
    return {
        "task": "Return strict JSON for 3D-RAMS intake.",
        "requiredStatuses": ["clarification_required", "confirmation_required", "launch_ready"],
        "safetyBoundary": SAFETY_BOUNDARY,
        "requiredFieldsBeforeLaunch": ["locationText or locationCandidate lat/lng", "areaScope", "userGoal"],
        "turn": turn,
    }


def _coerce_model_json(value: dict[str, Any] | str) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise IntakeValidationError("model output was not valid JSON.") from exc
    if not isinstance(parsed, dict):
        raise IntakeValidationError("model output JSON must be an object.")
    return parsed


def _deterministic_intake(turn: dict[str, Any]) -> dict[str, Any]:
    message = str(turn.get("message") or "")
    if not _has_site_signal(message):
        return {
            "status": "clarification_required",
            "assistantMessage": "I need a little more information before I can launch the 3D-RAMS supervisor.",
            "clarifyingQuestions": [
                "Which site, address, landmark, neighbourhood, or coordinate should I assess?",
                "What area should I cover around the site, for example a radius or boundary?",
                "What is the planned visit activity?",
            ],
        }

    scope = _area_scope(message)
    intake = {
        "locationText": _location_text(message),
        "locationCandidate": _location_candidate(message),
        "areaScope": scope,
        "userGoal": _goal(message),
        "userNotes": message,
        "materials": turn.get("materials") or [],
    }
    return {
        "status": "launch_ready" if turn.get("confirmedByUser") else "confirmation_required",
        "assistantMessage": (
            "I have enough information and will launch the supervisor workflow."
            if turn.get("confirmedByUser")
            else "I have enough information. Please confirm that I should launch the supervisor run."
        ),
        "confirmation": {"summary": _confirmation_summary(intake)},
        "intake": intake,
    }


def _validate_confirmed_intake(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise IntakeValidationError("intake must be an object.")
    location_text = _optional_text(value.get("locationText"))
    location_candidate = value.get("locationCandidate") if isinstance(value.get("locationCandidate"), dict) else {}
    has_coordinate = location_candidate.get("lat") is not None and location_candidate.get("lng") is not None
    if not location_text and not has_coordinate:
        raise IntakeValidationError("intake requires locationText or locationCandidate lat/lng.")
    area_scope = value.get("areaScope")
    if not isinstance(area_scope, dict) or area_scope.get("meters") is None:
        raise IntakeValidationError("intake.areaScope.meters is required.")
    user_goal = _optional_text(value.get("userGoal"))
    if not user_goal:
        raise IntakeValidationError("intake.userGoal is required.")
    materials = value.get("materials") or []
    if not isinstance(materials, list):
        raise IntakeValidationError("intake.materials must be a list.")
    normalized = {
        "locationText": location_text,
        "locationCandidate": location_candidate,
        "areaScope": {"type": str(area_scope.get("type") or "radius"), "meters": int(float(area_scope["meters"]))},
        "userGoal": user_goal,
        "userNotes": _optional_text(value.get("userNotes")) or "",
        "materials": materials,
    }
    return normalized


def _message_text(payload: dict[str, Any]) -> str:
    if payload.get("message") is not None:
        return str(payload["message"]).strip()
    if payload.get("prompt") is not None:
        return str(payload["prompt"]).strip()
    messages = payload.get("messages")
    if isinstance(messages, list):
        parts = []
        for message in messages:
            if isinstance(message, dict):
                content = message.get("content")
                if isinstance(content, str):
                    parts.append(content)
                elif isinstance(content, list):
                    parts.extend(str(item.get("text")) for item in content if isinstance(item, dict) and item.get("text"))
        return "\n".join(parts).strip()
    return ""


def _materials(payload: dict[str, Any]) -> list[dict[str, Any]]:
    runtime_options = payload.get("runtimeOptions") if isinstance(payload.get("runtimeOptions"), dict) else {}
    materials = payload.get("materials") or runtime_options.get("materials") or []
    return materials if isinstance(materials, list) else []


def _runtime_options(payload: dict[str, Any]) -> dict[str, Any]:
    options = dict(payload.get("runtimeOptions") or {}) if isinstance(payload.get("runtimeOptions"), dict) else {}
    options.setdefault("useBedrock", True)
    options.setdefault("includePlanningFixture", True)
    options.setdefault("simulateMapFailure", False)
    return options


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item is not None]


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _has_site_signal(message: str) -> bool:
    return bool(re.search(r"\b(albert embankment|street|road|lane|coordinate|near|site|lambeth)\b", message, re.I))


def _looks_like_confirmation(message: str) -> bool:
    normalized = message.strip().lower()
    return normalized in {"yes", "yes please", "confirm", "confirmed", "launch", "go", "go ahead"} or "confirm and launch" in normalized or "please launch" in normalized


def _area_scope(message: str) -> dict[str, Any]:
    km = re.search(r"(\d+(?:\.\d+)?)\s*km\b", message, re.I)
    if km:
        return {"type": "radius", "meters": int(float(km.group(1)) * 1000)}
    metres = re.search(r"(\d+(?:\.\d+)?)\s*(?:m|metre|meter|metres|meters)\b", message, re.I)
    if metres:
        return {"type": "radius", "meters": int(float(metres.group(1)))}
    return {"type": "radius", "meters": 800}


def _location_text(message: str) -> str:
    if re.search(r"8\s+albert\s+embankment", message, re.I):
        return "8 Albert Embankment"
    return message[:160] or "User supplied site"


def _location_candidate(message: str) -> dict[str, Any]:
    if re.search(r"8\s+albert\s+embankment", message, re.I):
        return {"label": "8 Albert Embankment", "lat": 51.492099, "lng": -0.118712, "confidence": 0.85}
    return {"label": _location_text(message), "confidence": 0.55}


def _goal(message: str) -> str:
    if re.search(r"\bsurvey\b", message, re.I):
        return "survey pre-visit review"
    return "pre-visit RAMS-style review"


def _confirmation_summary(intake: dict[str, Any]) -> str:
    location = intake.get("locationText") or intake.get("locationCandidate", {}).get("label") or "the selected site"
    meters = intake.get("areaScope", {}).get("meters")
    goal = intake.get("userGoal") or "pre-visit review"
    return f"Launch a 3D-RAMS supervisor review for {location}, covering a {meters}m radius for {goal}."


def _default_message(status: str) -> str:
    if status == "clarification_required":
        return "I need a little more information before I can launch the 3D-RAMS supervisor."
    if status == "confirmation_required":
        return "I have enough information. Please confirm that I should launch the supervisor run."
    return "I have enough information and will launch the supervisor workflow."
