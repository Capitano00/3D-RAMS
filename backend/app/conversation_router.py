from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from .bedrock_adapter import BedrockAdapterError, generate_bedrock_conversation_orchestration
from .config import RuntimeConfig
from .durable_runner import create_durable_run, read_durable_run
from .session_store import add_conversation_turn, get_session, llm_session_context, update_working_memory
from .site_intent import parse_site_intent


_TERMINAL_STATUSES = {
    "completed",
    "failed",
    "cancelled",
    "waiting_for_clarification",
    "waiting_for_location_confirmation",
    "waiting_for_approval",
}

_FOLLOW_UP_PHRASES = {
    "what do you mean",
    "what does that mean",
    "explain",
    "explain that",
    "why",
    "why is that",
    "what next",
    "what should i do",
}

_QUESTION_PREFIXES = {
    "what",
    "why",
    "how",
    "where",
    "when",
    "who",
    "which",
    "can",
    "could",
    "should",
    "would",
    "is",
    "are",
    "do",
    "does",
}

_STATUS_PHRASES = {
    "status",
    "where are we",
    "what is happening",
    "is it done",
    "are you done",
}

_CONFIRMATION_PHRASES = {"yes", "ok", "okay", "confirm", "confirmed", "looks right", "this is correct"}
_REJECTION_PHRASES = {
    "no",
    "not this site",
    "wrong site",
    "this is wrong",
    "not the right site",
    "that is not right",
    "that is wrong",
    "different site",
}
_START_OVER_PHRASES = {
    "start again",
    "start over",
    "new site",
    "reset",
    "clear this",
}
_GREETING_PHRASES = {
    "hello",
    "hi",
    "hey",
    "hiya",
    "good morning",
    "good afternoon",
    "good evening",
}
_HELP_PHRASES = {
    "help",
    "how does this work",
    "what can you do",
    "what do you need",
}


def handle_conversation_message(
    *,
    session_id: str,
    message: str,
    uploaded_file_ids: list[str],
    use_bedrock: bool,
    config: RuntimeConfig,
) -> dict[str, Any]:
    session = get_session(session_id, config)
    cleaned = " ".join(message.split())
    memory = session.setdefault("workingMemory", {})
    add_conversation_turn(
        session_id,
        role="user",
        text=cleaned,
        metadata={"routeInput": True},
        config=config,
    )

    intent = parse_site_intent(cleaned)
    deterministic_route = _classify_message(cleaned, memory, intent)
    orchestration = _maybe_orchestrate_conversation(
        session=session,
        message=cleaned,
        intent=intent,
        deterministic_route=deterministic_route,
        config=config,
    )
    route = _validated_route(orchestration, deterministic_route, memory, intent)
    if route in {"conversation", "greeting", "help"}:
        return _orchestrated_conversation_response(session_id, route, orchestration, memory, config)
    if route == "status":
        return _status_response(session_id, memory, config)
    if route == "follow_up":
        return _memory_response(session_id, cleaned, memory, config, orchestration=orchestration)
    if route == "confirm_by_chat":
        return _confirm_by_chat_response(session_id, memory, config)
    if route == "reject_location":
        return _reject_location_response(session_id, cleaned, memory, config)
    if route == "start_over_without_site":
        return _start_over_response(session_id, cleaned, memory, config)

    previous_active_run_id = memory.get("activeRunId")
    result = create_durable_run(
        session_id=session_id,
        message=cleaned,
        uploaded_file_ids=uploaded_file_ids,
        use_bedrock=use_bedrock,
        auto_start=True,
        config=config,
    )
    assistant_text = _assistant_text_from_run(result)
    add_conversation_turn(
        session_id,
        role="assistant",
        text=assistant_text,
        metadata={
            "route": "start_run",
            "conversationOrchestrator": _orchestration_metadata(orchestration),
            "runId": result.get("runId"),
            "runStatus": result.get("status"),
            "siteIntent": {
                "hasLocationEvidence": intent.get("hasLocationEvidence"),
                "namedSiteHint": intent.get("namedSiteHint"),
                "unsafeIntent": intent.get("unsafeIntent"),
            },
        },
        config=config,
    )
    result_payload = result.get("result") or {}
    update_fields: dict[str, Any] = {
        "activeRunId": result.get("runId"),
        "latestRunStatus": result.get("status"),
        "pendingUserAction": _pending_action(result),
        "latestLocationResolution": (result.get("locationResolution") or result_payload.get("locationResolution")),
        "latestReviewSummary": _latest_review_summary(result),
        "latestRoute": route,
    }
    if route in {"location_correction", "start_over_with_site"}:
        update_fields["previousRunId"] = previous_active_run_id
        update_fields["correctionReason"] = route
    update_working_memory(
        session_id,
        config,
        **update_fields,
    )
    return {
        "action": "started_run",
        "route": route if route != "new_run" else "new_or_guarded_run",
        "assistantMessage": assistant_text,
        "run": result,
        "runtime": _runtime_contract(config, "lambda-adapter-active"),
    }


def _classify_message(message: str, memory: dict[str, Any], intent: dict[str, Any]) -> str:
    lower = message.lower().strip(" ?.!")
    pending = memory.get("pendingUserAction")
    has_location_evidence = bool(intent.get("hasLocationEvidence"))
    has_site_signal = bool(intent.get("namedSiteHint") or has_location_evidence)
    if lower in _GREETING_PHRASES:
        return "greeting"
    if lower in _HELP_PHRASES:
        return "help"
    if lower in _STATUS_PHRASES or any(lower.startswith(f"{phrase} ") for phrase in _STATUS_PHRASES):
        return "status"
    if _starts_with_any(lower, _START_OVER_PHRASES):
        return "start_over_with_site" if has_site_signal else "start_over_without_site"
    if pending in {"confirm_or_correct_location", "provide_corrected_location"}:
        if has_location_evidence:
            return "location_correction"
        if pending == "confirm_or_correct_location" and lower in _CONFIRMATION_PHRASES:
            return "confirm_by_chat"
        if lower in _REJECTION_PHRASES or any(phrase in lower for phrase in _REJECTION_PHRASES):
            return "reject_location"
        if _looks_like_question(lower) and not has_location_evidence:
            return "follow_up"
        if _starts_with_any(lower, _FOLLOW_UP_PHRASES):
            return "follow_up"
        if not has_site_signal and not intent.get("unsafeIntent"):
            return "follow_up"
    elif pending and lower in _CONFIRMATION_PHRASES:
        return "follow_up"
    if _starts_with_any(lower, _FOLLOW_UP_PHRASES):
        return "follow_up"
    if _looks_like_question(lower) and memory.get("activeRunId") and not has_site_signal and not intent.get("unsafeIntent"):
        return "follow_up"
    return "new_run"


def _starts_with_any(lower: str, phrases: set[str]) -> bool:
    return lower in phrases or any(lower.startswith(f"{phrase} ") for phrase in phrases)


def _looks_like_question(lower: str) -> bool:
    if lower.endswith("?"):
        return True
    first = lower.split(" ", 1)[0] if lower else ""
    return first in _QUESTION_PREFIXES


def _maybe_orchestrate_conversation(
    *,
    session: dict[str, Any],
    message: str,
    intent: dict[str, Any],
    deterministic_route: str,
    config: RuntimeConfig,
) -> dict[str, Any] | None:
    if not config.bedrock_enabled:
        return None
    try:
        orchestration, metadata = generate_bedrock_conversation_orchestration(
            config=config,
            message=message,
            intent=intent,
            session_context=llm_session_context(session),
        )
        orchestration["metadata"] = metadata
        orchestration["fallbackRoute"] = deterministic_route
        return orchestration
    except (BedrockAdapterError, Exception) as exc:
        return {
            "route": deterministic_route,
            "assistantMessage": None,
            "shouldStartRun": deterministic_route in {"new_run", "location_correction", "start_over_with_site"},
            "pendingUserAction": None,
            "reason": f"Conversation orchestrator unavailable; deterministic route used. {exc}",
            "metadata": {"provider": "deterministic-fallback", "errorType": exc.__class__.__name__},
            "fallbackRoute": deterministic_route,
            "failed": True,
        }


def _validated_route(
    orchestration: dict[str, Any] | None,
    deterministic_route: str,
    memory: dict[str, Any],
    intent: dict[str, Any],
) -> str:
    if not orchestration:
        return deterministic_route

    route = str(orchestration.get("route") or deterministic_route).strip().lower().replace("-", "_")
    pending = memory.get("pendingUserAction")
    has_location_evidence = bool(intent.get("hasLocationEvidence"))
    has_site_signal = bool(intent.get("namedSiteHint") or has_location_evidence)

    if deterministic_route in {
        "status",
        "confirm_by_chat",
        "reject_location",
        "location_correction",
        "start_over_without_site",
        "start_over_with_site",
    }:
        return deterministic_route
    if pending in {"confirm_or_correct_location", "provide_corrected_location"}:
        if route in {"greeting", "help", "conversation", "follow_up"} and not has_location_evidence:
            return "follow_up"
        if not has_site_signal and not intent.get("unsafeIntent"):
            return "follow_up"
    if intent.get("unsafeIntent"):
        if orchestration.get("shouldStartRun") is False:
            return "conversation"
        return "new_run"
    if has_site_signal and deterministic_route in {"new_run", "location_correction", "start_over_with_site"}:
        return deterministic_route
    if route in {"new_run", "location_correction", "start_over_with_site"}:
        if has_site_signal or intent.get("unsafeIntent"):
            return "new_run" if route != "location_correction" else "location_correction"
        return "conversation"
    if not has_site_signal and not intent.get("unsafeIntent"):
        return route if route in {"conversation", "greeting", "help", "follow_up", "status"} else "conversation"
    if route in {"conversation", "greeting", "help", "follow_up", "status"}:
        return route
    return deterministic_route


def _orchestrated_conversation_response(
    session_id: str,
    route: str,
    orchestration: dict[str, Any] | None,
    memory: dict[str, Any],
    config: RuntimeConfig,
) -> dict[str, Any]:
    text = (
        (orchestration or {}).get("assistantMessage")
        or _deterministic_conversation_copy(route, memory)
    )
    pending_action = (orchestration or {}).get("pendingUserAction")
    add_conversation_turn(
        session_id,
        role="assistant",
        text=text,
        metadata={
            "route": route,
            "conversationOrchestrator": _orchestration_metadata(orchestration),
        },
        config=config,
    )
    update_fields: dict[str, Any] = {"latestRoute": route}
    if pending_action:
        update_fields["pendingUserAction"] = pending_action
    update_working_memory(session_id, config, **update_fields)
    return {
        "action": "answered_from_memory",
        "route": route,
        "assistantMessage": text,
        "runtime": _runtime_contract(
            config,
            "bedrock-conversation-orchestrator" if orchestration and not orchestration.get("failed") else "lambda-adapter-active",
        ),
    }


def _deterministic_conversation_copy(route: str, memory: dict[str, Any]) -> str:
    if route == "greeting":
        return (
            "Hi. Give me a UK postcode or latitude/longitude, plus the planned visit activity, "
            "and I will prepare a RAMS-style pre-visit review pack for human review."
        )
    if route == "help":
        return (
            "Send a UK postcode or latitude/longitude, the site type if known, and the planned activity "
            "such as survey, inspection, delivery, or maintenance."
        )
    if memory.get("pendingUserAction"):
        return f"I am waiting for: {memory['pendingUserAction']}."
    return "Tell me the site postcode or latitude/longitude, plus the planned visit activity, and I can prepare a pre-visit review pack for human review."


def _orchestration_metadata(orchestration: dict[str, Any] | None) -> dict[str, Any] | None:
    if not orchestration:
        return None
    metadata = orchestration.get("metadata") or {}
    return {
        "route": orchestration.get("route"),
        "shouldStartRun": orchestration.get("shouldStartRun"),
        "reason": orchestration.get("reason"),
        "provider": metadata.get("provider"),
        "phase": metadata.get("phase"),
        "modelCallCount": metadata.get("modelCallCount"),
        "fallbackRoute": orchestration.get("fallbackRoute"),
        "failed": orchestration.get("failed", False),
    }


def _looks_like_correction(lower: str) -> bool:
    return any(
        marker in lower
        for marker in [
            "corrected",
            "correction",
            "actually",
            "i meant",
            "use ",
            "try ",
            "instead",
            "the postcode is",
            "the coordinate is",
            "coordinates are",
            "lat",
            "latitude",
            "longitude",
        ]
    )


def _status_response(session_id: str, memory: dict[str, Any], config: RuntimeConfig) -> dict[str, Any]:
    run = _safe_read_run(memory.get("activeRunId"))
    if run:
        status = run.get("status")
        current_step = run.get("currentStep")
        text = f"The current run is {status} at `{current_step}`."
        if status == "waiting_for_location_confirmation":
            text += " I am waiting for you to confirm or correct the candidate location before review tools run."
        elif status == "waiting_for_clarification":
            text += " I need the missing site or visit detail before I can run tools."
        elif status == "completed":
            text += " The latest review pack is ready in the panels."
        add_conversation_turn(
            session_id,
            role="assistant",
            text=text,
            metadata={"route": "status", "runId": run.get("runId"), "runStatus": status},
            config=config,
        )
        update_working_memory(session_id, config, latestRunStatus=status)
        return {
            "action": "answered_from_memory",
            "route": "status",
            "assistantMessage": text,
            "run": run,
            "runtime": _runtime_contract(config, "lambda-adapter-active"),
        }
    text = "I do not have an active run in this session yet. Send a site visit request with a postcode or latitude/longitude to begin."
    add_conversation_turn(session_id, role="assistant", text=text, metadata={"route": "status"}, config=config)
    return {"action": "answered_from_memory", "route": "status", "assistantMessage": text, "runtime": _runtime_contract(config, "lambda-adapter-active")}


def _memory_response(
    session_id: str,
    message: str,
    memory: dict[str, Any],
    config: RuntimeConfig,
    *,
    orchestration: dict[str, Any] | None = None,
) -> dict[str, Any]:
    latest = memory.get("latestAssistantMessage")
    pending = memory.get("pendingUserAction")
    if orchestration and orchestration.get("assistantMessage"):
        text = orchestration["assistantMessage"]
    elif latest:
        text = (
            "I was referring to the previous step in this same session: "
            f"{latest} "
            "If that is unclear, provide a corrected postcode/coordinate or ask me about a specific panel such as location, evidence, risk, trace, or safety."
        )
    elif pending:
        text = f"I am waiting for: {pending}."
    else:
        text = "I do not have enough prior context in memory yet. Please send the site location and planned visit activity."
    add_conversation_turn(
        session_id,
        role="assistant",
        text=text,
        metadata={
            "route": "follow_up",
            "followUpPrompt": message[:120],
            "conversationOrchestrator": _orchestration_metadata(orchestration),
        },
        config=config,
    )
    return {
        "action": "answered_from_memory",
        "route": "follow_up",
        "assistantMessage": text,
        "runtime": _runtime_contract(config, "lambda-adapter-active"),
    }


def _confirm_by_chat_response(session_id: str, memory: dict[str, Any], config: RuntimeConfig) -> dict[str, Any]:
    text = (
        "I am still waiting for explicit location confirmation through the candidate card. "
        "Use `Confirm this site` to start map, evidence, risk, and briefing tools, or provide a corrected postcode/coordinate if the candidate is wrong."
    )
    add_conversation_turn(
        session_id,
        role="assistant",
        text=text,
        metadata={"route": "confirm_by_chat", "runId": memory.get("activeRunId")},
        config=config,
    )
    update_working_memory(session_id, config, pendingUserAction="confirm_or_correct_location", latestRoute="confirm_by_chat")
    return {
        "action": "answered_from_memory",
        "route": "confirm_by_chat",
        "assistantMessage": text,
        "runtime": _runtime_contract(config, "lambda-adapter-active"),
    }


def _reject_location_response(
    session_id: str,
    message: str,
    memory: dict[str, Any],
    config: RuntimeConfig,
) -> dict[str, Any]:
    text = (
        "Understood. I will not run the site-review tools for that candidate. "
        "Please provide a corrected UK postcode, latitude/longitude, OS grid reference, nearest road/town, or public evidence for the intended site."
    )
    add_conversation_turn(
        session_id,
        role="assistant",
        text=text,
        metadata={"route": "reject_location", "rejectionPrompt": message[:120], "runId": memory.get("activeRunId")},
        config=config,
    )
    update_working_memory(
        session_id,
        config,
        pendingUserAction="provide_corrected_location",
        latestRoute="reject_location",
        rejectedRunId=memory.get("activeRunId"),
    )
    return {
        "action": "answered_from_memory",
        "route": "reject_location",
        "assistantMessage": text,
        "runtime": _runtime_contract(config, "lambda-adapter-active"),
    }


def _start_over_response(session_id: str, message: str, memory: dict[str, Any], config: RuntimeConfig) -> dict[str, Any]:
    text = (
        "I can start a fresh site review. Send the new site request with a UK postcode, latitude/longitude, or a clear named site plus supporting location detail."
    )
    add_conversation_turn(
        session_id,
        role="assistant",
        text=text,
        metadata={"route": "start_over_without_site", "prompt": message[:120], "previousRunId": memory.get("activeRunId")},
        config=config,
    )
    update_working_memory(
        session_id,
        config,
        pendingUserAction="provide_new_site_request",
        latestRoute="start_over_without_site",
        previousRunId=memory.get("activeRunId"),
        activeRunId=None,
        latestRunStatus=None,
    )
    return {
        "action": "answered_from_memory",
        "route": "start_over_without_site",
        "assistantMessage": text,
        "runtime": _runtime_contract(config, "lambda-adapter-active"),
    }


def _safe_read_run(run_id: str | None) -> dict[str, Any] | None:
    if not run_id:
        return None
    try:
        return read_durable_run(run_id)
    except HTTPException:
        return None


def _assistant_text_from_run(run: dict[str, Any]) -> str:
    result = run.get("result") or {}
    if result.get("assistantMessage"):
        return result["assistantMessage"]
    status = run.get("status")
    current_step = run.get("currentStep")
    if status in {"queued", "running"}:
        return f"I have started the site review and am currently at `{current_step}`."
    return f"Run {status}: {current_step}."


def _pending_action(run: dict[str, Any]) -> str | None:
    status = run.get("status")
    if status == "waiting_for_location_confirmation":
        result_payload = run.get("result") or {}
        location_resolution = run.get("locationResolution") or result_payload.get("locationResolution") or {}
        if location_resolution.get("locationCandidates"):
            return "confirm_or_correct_location"
        return "provide_location_detail"
    if status == "waiting_for_clarification":
        return "answer_clarifying_question"
    if status in {"queued", "running"}:
        return "wait_for_agent_run"
    return None


def _latest_review_summary(run: dict[str, Any]) -> dict[str, Any] | None:
    result = run.get("result") or {}
    briefing = result.get("briefing") or result.get("uiState", {}).get("briefing")
    if not briefing:
        return None
    return {
        "headline": briefing.get("headline"),
        "generationMode": briefing.get("generation_mode") or briefing.get("generationMode"),
        "runId": run.get("runId"),
        "status": run.get("status"),
    }


def _runtime_contract(config: RuntimeConfig, status: str) -> dict[str, Any]:
    return {
        "agentRuntimeTarget": "agentcore",
        "agentRuntimeStatus": status,
        "adapter": "api-gateway-lambda-fastapi",
        "guardsFirst": True,
        "memoryMode": "bounded-session-working-memory",
        "bedrockEnabled": config.bedrock_enabled,
        "awsRegion": config.aws_region,
    }
