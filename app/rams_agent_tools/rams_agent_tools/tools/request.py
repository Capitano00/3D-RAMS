from __future__ import annotations

import hashlib
import json
from typing import Any

from ..config import RuntimeConfig
from .materials import sanitize_material_references
from .telemetry import trace_step


DEFAULT_SYNTHETIC_LATITUDE = 52.2053
DEFAULT_SYNTHETIC_LONGITUDE = -1.6022
LOCATION_CONFIRMATION_PROMPT = (
    "Please confirm the site before I run map, evidence, risk, or briefing tools. "
    "Send a postcode, coordinates, OS grid reference, nearest road/town, local authority, "
    "or another trusted source."
)


def normalize_request(request: dict[str, Any]) -> dict[str, Any]:
    fixture_pack = request.get("fixturePack") or request.get("fixture_pack")
    agent_mode = str(request.get("agentMode") or request.get("agent_mode") or "llm-planner").strip().lower()
    case_id = request.get("caseId") or None
    materials = sanitize_material_references(request.get("materials"))
    upstream = request.get("agentcoreUpstream") if isinstance(request.get("agentcoreUpstream"), dict) else {}
    area_scope = request.get("areaScope") or upstream.get("areaScope")
    candidate = _dict(request.get("locationCandidate"))
    site = _dict(request.get("site"))
    latitude_value = _first_present(
        request.get("latitude"),
        request.get("lat"),
        candidate.get("latitude"),
        candidate.get("lat"),
        site.get("latitude"),
        site.get("lat"),
    )
    longitude_value = _first_present(
        request.get("longitude"),
        request.get("lng"),
        candidate.get("longitude"),
        candidate.get("lng"),
        site.get("longitude"),
        site.get("lon"),
        site.get("lng"),
    )
    has_explicit_coordinates = latitude_value is not None and longitude_value is not None
    location_text = _optional_text(request.get("locationText") or candidate.get("label") or site.get("label"))
    if case_id:
        for material in materials:
            material.setdefault("caseId", case_id)
    normalized = {
        "caseId": case_id,
        "siteName": request.get("siteName") or location_text or "Demo rural field fixture",
        "latitude": float(latitude_value if latitude_value is not None else DEFAULT_SYNTHETIC_LATITUDE),
        "longitude": float(longitude_value if longitude_value is not None else DEFAULT_SYNTHETIC_LONGITUDE),
        "goal": request.get("goal") or "Pre-visit RAMS scoping pack",
        "includePlanningFixture": bool(request.get("includePlanningFixture", True)),
        "simulateMapFailure": bool(request.get("simulateMapFailure")),
        "useBedrock": bool(request.get("useBedrock", True)),
        "agentMode": agent_mode or "llm-planner",
        "fixturePack": str(fixture_pack).strip().lower() if fixture_pack else None,
        "additionalRequest": request.get("additionalRequest") or "",
        "materials": materials,
        "locationText": location_text,
        "locationCandidate": candidate,
        "locationConfirmation": _location_confirmation(request, upstream),
        "_hasExplicitCoordinates": has_explicit_coordinates,
        "_hasLocationEvidence": has_explicit_coordinates or bool(location_text or request.get("siteName") or site),
    }
    if isinstance(area_scope, dict) and area_scope:
        normalized["areaScope"] = _area_scope(area_scope)
    access_context = request.get("accessContext")
    if isinstance(access_context, dict):
        normalized["accessContext"] = access_context
    return normalized


def location_confirmation_gate(
    request: dict[str, Any],
    normalized: dict[str, Any],
    fixture_pack: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if fixture_pack:
        normalized["locationConfirmation"] = {
            "status": "not_required",
            "required": False,
            "dataMode": "cached-public-fixture",
            "reason": "Cached public fixture-pack location metadata is already source-labelled.",
        }
        return None
    if not normalized.get("_hasLocationEvidence"):
        normalized["locationConfirmation"] = {
            "status": "not_required",
            "required": False,
            "dataMode": "synthetic-fixture",
            "reason": "Explicit Demo1 synthetic fixture path.",
        }
        return None

    confirmation = _dict(normalized.get("locationConfirmation"))
    candidate = _candidate_payload(request, normalized)
    if _is_confirmed(confirmation) or _is_confirmed_site_object(request, normalized):
        confirmation.update(
            {
                "status": "confirmed",
                "required": False,
                "candidate": candidate,
                "candidates": [candidate],
            }
        )
        normalized["locationConfirmation"] = confirmation
        normalized["locationCandidate"] = candidate
        return None

    status = "confirmation_required" if candidate.get("latitude") is not None else "evidence_required"
    confirmation = {
        "status": status,
        "required": True,
        "message": LOCATION_CONFIRMATION_PROMPT,
        "candidates": [candidate],
    }
    return {
        "confirmation": confirmation,
        "trace": trace_step(
            "location_confirmation_gate",
            "blocked",
            "Paused before site-specific tools because the location is not confirmed.",
            {"locationConfirmation": confirmation},
            source_ids=["user-request", candidate["sourceId"]],
            evidence_ids=[f"ev-{candidate['candidateId']}"],
        ),
        "evidence": {
            "id": f"ev-{candidate['candidateId']}",
            "title": f"Location candidate: {candidate['label']}",
            "status": "provisional-location-candidate",
            "summary": candidate["reason"],
            "sourceIds": ["user-request", candidate["sourceId"]],
            "candidate": candidate,
        },
        "source": {
            "id": candidate["sourceId"],
            "label": candidate["source"],
            "kind": "location_candidate",
            "status": candidate["dataMode"],
            "origin": candidate["source"],
            "trustBoundary": "Requires operator confirmation before site-specific tools run",
            "awsMapping": "DynamoDB pending location candidate in future runtime",
        },
    }


def _area_scope(value: dict[str, Any]) -> dict[str, Any]:
    scope_type = str(value.get("type") or "radius").strip() or "radius"
    try:
        meters = int(float(value.get("meters", 0)))
    except (TypeError, ValueError):
        meters = 0
    return {"type": scope_type, "meters": meters} if meters > 0 else {"type": scope_type}


def source_register(
    include_planning_fixture: bool,
    simulate_map_failure: bool,
    bedrock_status: str,
    config: RuntimeConfig,
    fixture_pack: dict[str, Any] | None = None,
    planner_status: str = "deterministic",
    location_confirmation: dict[str, Any] | None = None,
    planning_data: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = [
        {
            "id": "user-request",
            "label": "Submitted coordinate and options",
            "kind": "request",
            "status": "real",
            "origin": "Browser form payload",
            "trustBoundary": "User input",
            "awsMapping": "DynamoDB run record",
        },
    ]

    confirmed_candidate = _dict(location_confirmation).get("candidate") if isinstance(location_confirmation, dict) else None
    if fixture_pack:
        sources.extend(fixture_pack.get("sources", []))
        if simulate_map_failure:
            sources.append(
                {
                    "id": "geo-fallback",
                    "label": "Fallback geospatial fixture",
                    "kind": "geospatial_features",
                    "status": "fallback",
                    "origin": "fixtures/geospatial_features.json",
                    "trustBoundary": "Public-safe synthetic fixture",
                    "awsMapping": "S3 evidence object plus CloudWatch source metadata",
                }
            )
    elif isinstance(confirmed_candidate, dict):
        sources.extend(
            [
                {
                    "id": confirmed_candidate.get("sourceId") or "confirmed-location-candidate",
                    "label": confirmed_candidate.get("source") or "Confirmed location candidate",
                    "kind": "location",
                    "status": confirmed_candidate.get("dataMode") or "user-supplied-confirmed",
                    "origin": confirmed_candidate.get("source") or "Operator-confirmed request payload",
                    "trustBoundary": "Operator-confirmed location evidence",
                    "awsMapping": "DynamoDB site/session metadata",
                },
                {
                    "id": "geo-fixture",
                    "label": "Mock geospatial feature pack",
                    "kind": "geospatial_features",
                    "status": "mocked",
                    "origin": "fixtures/geospatial_features.json",
                    "trustBoundary": "Public-safe synthetic fixture around confirmed coordinate",
                    "awsMapping": "S3 evidence object plus CloudWatch source metadata",
                },
            ]
        )
    else:
        sources.extend(
            [
                {
                    "id": "location-fixture",
                    "label": "Synthetic local authority fixture",
                    "kind": "location",
                    "status": "mocked",
                    "origin": "AgentCore deterministic defaults",
                    "trustBoundary": "Public-safe demo fixture",
                    "awsMapping": "DynamoDB site/session metadata",
                },
                {
                    "id": "geo-fallback" if simulate_map_failure else "geo-fixture",
                    "label": "Fallback geospatial fixture" if simulate_map_failure else "Mock geospatial feature pack",
                    "kind": "geospatial_features",
                    "status": "fallback" if simulate_map_failure else "mocked",
                    "origin": "fixtures/geospatial_features.json",
                    "trustBoundary": "Public-safe synthetic fixture",
                    "awsMapping": "S3 evidence object plus CloudWatch source metadata",
                },
            ]
        )

    sources.extend(
        [
            {
                "id": "cesium-local",
                "label": "Local Cesium scene configuration",
                "kind": "3d_scene",
                "status": "real",
                "origin": "Frontend CesiumJS with AgentCore scene config",
                "trustBoundary": "Browser rendering",
                "awsMapping": "CloudFront/static frontend plus AgentCore Runtime",
            },
            {
                "id": "bedrock-planner",
                "label": "Live model supervisor planner",
                "kind": "llm_planner",
                "status": planner_status,
                "origin": (
                    f"{config.openai_model_id} via OpenAI-compatible gateway"
                    if config.llm_provider == "openai" and config.bedrock_enabled
                    else f"{config.bedrock_model_id} in {config.aws_region}"
                    if config.bedrock_enabled
                    else "Deterministic/mock planner unless ENABLE_LIVE_MODEL=true and the run requests live model use"
                ),
                "trustBoundary": "Hosted model gateway boundary when enabled",
                "awsMapping": "Hosted OpenAI-compatible gateway for supervisor subagent planning",
            },
            {
                "id": "bedrock-briefing",
                "label": "Live model briefing adapter",
                "kind": "llm_adapter",
                "status": bedrock_status,
                "origin": (
                    f"{config.openai_model_id} via OpenAI-compatible gateway"
                    if config.llm_provider == "openai" and config.bedrock_enabled
                    else f"{config.bedrock_model_id} in {config.aws_region}"
                    if config.bedrock_enabled
                    else "Disabled unless ENABLE_LIVE_MODEL=true and the run requests live model use"
                ),
                "trustBoundary": "Hosted model gateway boundary when enabled",
                "awsMapping": "Hosted OpenAI-compatible gateway for one briefing step per run",
            },
        ]
    )
    if planning_data and planning_data.get("status") in {"live", "partial", "failed"}:
        sources.append(
            {
                "id": "planning-data-api",
                "label": "Planning Data live feature lookup",
                "kind": "planning_data_features",
                "status": planning_data.get("status"),
                "origin": planning_data.get("endpoint") or "https://www.planning.data.gov.uk/entity.json",
                "trustBoundary": "Official public Planning Data API; default-off optional live lookup after confirmed location",
                "awsMapping": "Future cached evidence object plus CloudWatch source metadata",
                "attribution": planning_data.get("attribution"),
                "freshness": planning_data.get("freshness"),
            }
        )

    if not fixture_pack:
        sources.append(
            {
                "id": "planning-fixture",
                "label": "Synthetic nearby planning report extract",
                "kind": "planning_document",
                "status": "mocked" if include_planning_fixture else "unavailable",
                "origin": "fixtures/planning_report.txt" if include_planning_fixture else "Disabled by tester",
                "trustBoundary": "Public-safe synthetic fixture",
                "awsMapping": "S3 evidence object and Bedrock extraction input",
            }
        )
    return sources


def _candidate_payload(request: dict[str, Any], normalized: dict[str, Any]) -> dict[str, Any]:
    candidate = _dict(normalized.get("locationCandidate"))
    source, source_id, data_mode = _candidate_source(request, normalized)
    payload = {
        "candidateId": _candidate_id(normalized),
        "label": normalized.get("siteName") or candidate.get("label") or "Unconfirmed site",
        "latitude": normalized.get("latitude") if normalized.get("_hasExplicitCoordinates") else None,
        "longitude": normalized.get("longitude") if normalized.get("_hasExplicitCoordinates") else None,
        "source": source,
        "sourceId": source_id,
        "confidence": candidate.get("confidence") or ("medium" if normalized.get("_hasExplicitCoordinates") else "low"),
        "dataMode": data_mode,
        "reason": (
            "Coordinates were supplied by the request but need explicit operator confirmation before site-specific tools run."
            if normalized.get("_hasExplicitCoordinates")
            else LOCATION_CONFIRMATION_PROMPT
        ),
    }
    return {key: value for key, value in payload.items() if value is not None}


def _candidate_source(request: dict[str, Any], normalized: dict[str, Any]) -> tuple[str, str, str]:
    if request.get("locationCandidate"):
        return "ASI/entry-agent location candidate", "entry-location-candidate", "entry-agent-candidate"
    if request.get("site"):
        return "ASI-provided site object", "asi-site-object", "asi-provided"
    if normalized.get("_hasExplicitCoordinates"):
        return "User-supplied coordinates", "user-supplied-coordinate", "user-supplied"
    return "User-supplied location text", "user-supplied-location-text", "user-supplied"


def _candidate_id(normalized: dict[str, Any]) -> str:
    seed = {
        "label": normalized.get("siteName"),
        "latitude": normalized.get("latitude") if normalized.get("_hasExplicitCoordinates") else None,
        "longitude": normalized.get("longitude") if normalized.get("_hasExplicitCoordinates") else None,
        "locationText": normalized.get("locationText"),
    }
    digest = hashlib.sha256(json.dumps(seed, sort_keys=True, default=str).encode("utf-8")).hexdigest()
    return f"location-candidate-{digest[:10]}"


def _location_confirmation(request: dict[str, Any], upstream: dict[str, Any]) -> dict[str, Any]:
    confirmation = _dict(request.get("locationConfirmation") or upstream.get("locationConfirmation"))
    if request.get("locationConfirmed") is True:
        confirmation["status"] = "confirmed"
    if confirmation:
        return confirmation
    return {}


def _is_confirmed(confirmation: dict[str, Any]) -> bool:
    return str(confirmation.get("status") or "").strip().lower() in {"confirmed", "accepted", "approved"}


def _is_confirmed_site_object(request: dict[str, Any], normalized: dict[str, Any]) -> bool:
    return bool(request.get("site") and normalized.get("_hasExplicitCoordinates"))


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _first_present(*values: Any) -> Any:
    for value in values:
        if value is not None and value != "":
            return value
    return None
