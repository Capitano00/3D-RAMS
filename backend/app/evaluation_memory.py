from __future__ import annotations

import hashlib
import time
from typing import Any

from .site_intent import parse_site_intent


SAFE_EVALUATION_MEMORY_NOTE = (
    "Product-quality metadata only. It is not certified RAMS, safety evidence, "
    "emergency guidance, or approval-to-work evidence."
)


def build_evaluation_summary(run: dict[str, Any], result: dict[str, Any] | None = None) -> dict[str, Any]:
    stored_result = run.get("result") if isinstance(run.get("result"), dict) else {}
    result = result if isinstance(result, dict) and result else stored_result or {}
    request = run.get("request") or {}
    message_summary = str(request.get("messageSummary") or "")
    raw_message = str(request.get("message") or message_summary)
    intent = parse_site_intent(raw_message)
    status = str(run.get("status") or result.get("status") or "unknown")
    result_ui_state = result.get("uiState") if isinstance(result.get("uiState"), dict) else {}
    location_resolution = run.get("locationResolution") or result.get("locationResolution") or result_ui_state.get("locationResolution") or {}
    ui_state = result_ui_state or run.get("finalUiState") or run.get("partialUiState") or {}
    if not isinstance(ui_state, dict):
        ui_state = {}
    evaluation = result.get("evaluation") or ui_state.get("evaluation") or {}
    scores = evaluation.get("scores") if isinstance(evaluation, dict) else {}
    safety = result.get("safety") or ui_state.get("safety") or run.get("safetyResult") or {}
    if not isinstance(safety, dict):
        safety = {}
    input_mode = _input_mode(intent, run, result, location_resolution)
    site_type = _site_type(intent, run, result, ui_state)
    confirmation_required = _confirmation_required(status, location_resolution, result)
    confirmation_completed = _confirmation_completed(run, result, location_resolution)
    safety_passed = bool(safety.get("allowed", True)) and safety.get("level") != "blocked"
    tools_started_before_confirmation = _tools_started_before_confirmation(run, confirmation_required, confirmation_completed)
    failure_tags = _failure_tags(
        status=status,
        input_mode=input_mode,
        run=run,
        result=result,
        location_resolution=location_resolution,
        evaluation=evaluation if isinstance(evaluation, dict) else {},
        safety=safety,
        tools_started_before_confirmation=tools_started_before_confirmation,
    )
    user_confusion_tags = _user_confusion_tags(run, result)
    data_mode = _data_mode(run, result, ui_state, location_resolution)
    grounding_score = _score(scores, "grounding", fallback=_fallback_score(input_mode, status, "grounding"))
    relevance_score = _score(scores, "relevance", fallback=_fallback_score(input_mode, status, "relevance"))
    completeness_score = _score(scores, "completeness", fallback=_fallback_score(input_mode, status, "completeness"))

    return {
        "runId": run.get("runId"),
        "sessionRef": _session_ref(run.get("sessionId")),
        "timestamp": run.get("updatedAt") or _now_iso(),
        "inputMode": input_mode,
        "siteType": site_type,
        "runStatus": status,
        "locationResolved": bool(ui_state.get("location") or run.get("confirmedLocation") or location_resolution.get("confirmedLocation")),
        "confirmationRequired": confirmation_required,
        "confirmationCompleted": confirmation_completed,
        "toolsStartedBeforeConfirmation": tools_started_before_confirmation,
        "groundingScore": grounding_score,
        "relevanceScore": relevance_score,
        "completenessScore": completeness_score,
        "safetyPassed": safety_passed,
        "failureTags": failure_tags,
        "userConfusionTags": user_confusion_tags,
        "dataMode": data_mode,
        "recommendedNextAction": _recommended_next_action(
            status=status,
            input_mode=input_mode,
            safety_passed=safety_passed,
            failure_tags=failure_tags,
            confirmation_required=confirmation_required,
            confirmation_completed=confirmation_completed,
        ),
        "recommendedNextTest": _recommended_next_test(
            input_mode=input_mode,
            site_type=site_type,
            safety_passed=safety_passed,
            failure_tags=failure_tags,
            user_confusion_tags=user_confusion_tags,
            data_mode=data_mode,
        ),
        "privacyBoundary": SAFE_EVALUATION_MEMORY_NOTE,
    }


def add_user_confusion_tag(summary: dict[str, Any] | None, tag: str) -> dict[str, Any] | None:
    if not isinstance(summary, dict) or not summary:
        return summary
    tags = list(summary.get("userConfusionTags") or [])
    if tag not in tags:
        tags.append(tag)
    updated = {**summary, "userConfusionTags": tags, "timestamp": _now_iso()}
    if tag == "follow_up_confusion":
        updated["recommendedNextTest"] = "follow_up_confusion_regression"
        updated["recommendedNextAction"] = "tighten pending-action copy and rerun follow-up confusion test"
        return updated
    if not updated.get("recommendedNextTest") or updated["recommendedNextTest"] == "repeat_happy_path_regression":
        updated["recommendedNextTest"] = "follow_up_confusion_regression"
    if not updated.get("recommendedNextAction") or updated["recommendedNextAction"] == "monitor_recurring_quality_patterns":
        updated["recommendedNextAction"] = "tighten_pending-action copy and rerun follow-up confusion test"
    return updated


def _input_mode(
    intent: dict[str, Any],
    run: dict[str, Any],
    result: dict[str, Any],
    location_resolution: dict[str, Any],
) -> str:
    lower = str(run.get("request", {}).get("message") or "").lower()
    if intent.get("unsafeIntent") or (result.get("safety") or {}).get("level") == "blocked":
        return "unsafe"
    if any(marker in lower for marker in ("actually", "i meant", "instead", "corrected", "correction", "not this site")):
        return "correction"
    if intent.get("coordinate") or _candidate_source(location_resolution) == "user-supplied-coordinate":
        return "coordinate"
    if intent.get("postcode") or intent.get("outcode"):
        return "postcode"
    if intent.get("knownPublicFixture") or run.get("request", {}).get("fixturePack") or result.get("runtime", {}).get("fixturePack"):
        return "fixture"
    if intent.get("siteName") or intent.get("namedSiteHint") or intent.get("vagueLocationHint"):
        return "name_only"
    return "fixture" if result.get("runtime", {}).get("fixturePackMode") == "cached-public-fixture" else "name_only"


def _site_type(intent: dict[str, Any], run: dict[str, Any], result: dict[str, Any], ui_state: dict[str, Any]) -> str:
    site_types = [str(item) for item in intent.get("siteTypes", [])]
    if "solar" in site_types:
        return "solar"
    if "quarry" in site_types:
        return "quarry"
    if "rural_field" in site_types:
        return "rural"
    if site_types:
        return site_types[0]
    location = ui_state.get("location")
    if not isinstance(location, dict):
        location = {}
    briefing = result.get("briefing")
    if not isinstance(briefing, dict):
        briefing = {}
    text = " ".join(
        [
            str(run.get("request", {}).get("messageSummary") or ""),
            str(location.get("label") or ""),
            str(briefing.get("site") or ""),
        ]
    ).lower()
    if any(term in text for term in ("solar", " pv ", "photovoltaic", "inverter")):
        return "solar"
    if "quarry" in text or "aggregate" in text:
        return "quarry"
    if any(term in text for term in ("lambeth", "embankment", "urban", "city", "town centre")):
        return "urban"
    if any(term in text for term in ("farm", "field", "rural", "pasture")):
        return "rural"
    return "unknown"


def _confirmation_required(status: str, location_resolution: dict[str, Any], result: dict[str, Any]) -> bool:
    return bool(
        status == "waiting_for_location_confirmation"
        or result.get("needsLocationConfirmation")
        or location_resolution.get("needsLocationConfirmation")
        or location_resolution.get("confirmedLocation")
    )


def _confirmation_completed(run: dict[str, Any], result: dict[str, Any], location_resolution: dict[str, Any]) -> bool:
    return bool(run.get("confirmedLocation") or result.get("confirmedLocation") or location_resolution.get("confirmedLocation"))


def _tools_started_before_confirmation(run: dict[str, Any], confirmation_required: bool, confirmation_completed: bool) -> bool:
    if not confirmation_required:
        return False
    tool_results = list(run.get("toolResults") or [])
    if not tool_results:
        return False
    if not confirmation_completed:
        return True
    steps = list(run.get("steps") or [])
    first_tool_index = _first_index(steps, lambda step: str(step.get("name", "")).startswith("tool:"))
    confirmation_index = _first_index(steps, lambda step: step.get("name") == "location_confirmation" and step.get("status") == "ok")
    return first_tool_index is not None and (confirmation_index is None or first_tool_index < confirmation_index)


def _failure_tags(
    *,
    status: str,
    input_mode: str,
    run: dict[str, Any],
    result: dict[str, Any],
    location_resolution: dict[str, Any],
    evaluation: dict[str, Any],
    safety: dict[str, Any],
    tools_started_before_confirmation: bool,
) -> list[str]:
    tags: list[str] = []
    if status in {"failed", "cancelled"}:
        tags.append(f"run_{status}")
    if input_mode == "unsafe" or safety.get("level") == "blocked":
        tags.append("safety_blocked")
    if status == "waiting_for_location_evidence" or (input_mode == "name_only" and result.get("needsLocationEvidence")):
        tags.append("location_evidence_needed")
    if status == "waiting_for_location_confirmation" or result.get("needsLocationConfirmation"):
        tags.append("confirmation_pending")
    if status == "waiting_for_clarification":
        tags.append("clarification_needed")
    if tools_started_before_confirmation:
        tags.append("tools_started_before_confirmation")
    if evaluation.get("passed") is False:
        tags.append("output_quality_below_threshold")
    for issue in evaluation.get("issues") or []:
        code = issue.get("code")
        if code:
            tags.append(str(code))
    if run.get("fallbackReason") or (result.get("fallback") or {}).get("status") == "fallback":
        tags.append("fallback_used")
    if location_resolution.get("resolverMode") == "conversation-location-needed":
        tags.append("conversation_location_needed")
    return _dedupe(tags)


def _user_confusion_tags(run: dict[str, Any], result: dict[str, Any]) -> list[str]:
    tags: list[str] = []
    if result.get("needsClarification"):
        tags.append("agent_requested_user_input")
    if result.get("needsLocationEvidence"):
        tags.append("site_name_without_location_evidence")
    if result.get("needsLocationConfirmation"):
        tags.append("candidate_confirmation_needed")
    if run.get("currentStep") == "waiting_for_clarification":
        tags.append("missing_site_or_visit_detail")
    return _dedupe(tags)


def _data_mode(
    run: dict[str, Any],
    result: dict[str, Any],
    ui_state: dict[str, Any],
    location_resolution: dict[str, Any],
) -> str:
    runtime = result.get("runtime") or run.get("runtime") or {}
    if runtime.get("liveApiCalls"):
        return "mixed" if runtime.get("fixturePack") or runtime.get("fixturePackMode") else "live"
    candidate_modes = [candidate.get("dataMode") for candidate in location_resolution.get("locationCandidates") or [] if isinstance(candidate, dict)]
    if any(mode in {"source-labelled-location", "source-labelled-coordinate"} for mode in candidate_modes):
        return "live" if any("postcodes" in str((candidate.get("source") or "")) for candidate in location_resolution.get("locationCandidates") or []) else "synthetic"
    if runtime.get("fixturePackMode") == "cached-public-fixture" or runtime.get("fixturePack"):
        return "cached"
    feature_modes = {
        str(feature.get("dataMode") or feature.get("featureMode") or "")
        for feature in (ui_state.get("mapFeatures") or [])
        if isinstance(feature, dict)
    }
    if any("live" in mode for mode in feature_modes):
        return "mixed" if any("synthetic" in mode or "cached" in mode for mode in feature_modes) else "live"
    if any("cached" in mode for mode in feature_modes):
        return "cached"
    return "synthetic"


def _recommended_next_action(
    *,
    status: str,
    input_mode: str,
    safety_passed: bool,
    failure_tags: list[str],
    confirmation_required: bool,
    confirmation_completed: bool,
) -> str:
    if not safety_passed or "safety_blocked" in failure_tags:
        return "keep blocked; test safe reformulation path"
    if "tools_started_before_confirmation" in failure_tags:
        return "fix confirmation gate before running more demos"
    if "location_evidence_needed" in failure_tags or input_mode == "name_only":
        return "ask for postcode, coordinate, or public source before review tools"
    if confirmation_required and not confirmation_completed:
        return "wait for candidate confirmation before tool execution"
    if status == "failed":
        return "inspect failed step and rerun bounded regression"
    if "output_quality_below_threshold" in failure_tags:
        return "review evaluator issues and rerun repair-loop regression"
    return "monitor recurring quality patterns"


def _recommended_next_test(
    *,
    input_mode: str,
    site_type: str,
    safety_passed: bool,
    failure_tags: list[str],
    user_confusion_tags: list[str],
    data_mode: str,
) -> str:
    if not safety_passed or "safety_blocked" in failure_tags:
        return "unsafe_request_block_regression"
    if "site_name_without_location_evidence" in user_confusion_tags or input_mode == "name_only":
        return "name_only_location_evidence_regression"
    if input_mode == "coordinate":
        return f"coordinate_{site_type}_label_regression" if site_type != "unknown" else "coordinate_site_type_regression"
    if input_mode == "postcode":
        return "postcode_confirmation_regression"
    if data_mode == "mixed":
        return "mixed_data_mode_trace_regression"
    return "repeat_happy_path_regression"


def _score(scores: Any, key: str, *, fallback: float) -> float:
    if isinstance(scores, dict) and key in scores:
        try:
            return round(float(scores[key]), 3)
        except (TypeError, ValueError):
            pass
    return fallback


def _fallback_score(input_mode: str, status: str, key: str) -> float:
    if input_mode == "unsafe":
        return 0.0 if key in {"grounding", "completeness"} else 0.4
    if status in {"waiting_for_location_evidence", "waiting_for_location_confirmation", "waiting_for_clarification"}:
        defaults = {"grounding": 0.25, "relevance": 0.7, "completeness": 0.35}
        return defaults[key]
    if status == "failed":
        return 0.0
    return 1.0


def _candidate_source(location_resolution: dict[str, Any]) -> str | None:
    candidates = location_resolution.get("locationCandidates") or []
    if not candidates:
        return None
    first = candidates[0] if isinstance(candidates[0], dict) else {}
    return first.get("source")


def _first_index(items: list[dict[str, Any]], predicate: Any) -> int | None:
    for index, item in enumerate(items):
        if predicate(item):
            return index
    return None


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _session_ref(session_id: Any) -> str:
    text = str(session_id or "unknown-session")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
    return f"session-sha256-{digest}"


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
