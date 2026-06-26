from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .fixtures import load_json, load_text


AWS_TRACE_MAPPING = {
    "resolve_location": "CloudWatch span: tool.resolve_location",
    "load_geospatial_features": "CloudWatch span: tool.load_geospatial_features",
    "build_scene_config": "CloudWatch span: tool.build_scene_config",
    "load_planning_context": "CloudWatch span: tool.load_planning_context",
    "extract_hazard_notes": "Bedrock/CloudWatch span: tool.extract_hazard_notes",
    "create_annotations": "CloudWatch span: tool.create_annotations",
    "generate_site_brief": "Bedrock/CloudWatch span: tool.generate_site_brief",
    "safety_gate": "Guardrails/CloudWatch span: tool.safety_gate",
}


def trace_step(
    name: str,
    status: str,
    summary: str,
    output: dict[str, Any],
    *,
    source_ids: list[str] | None = None,
    evidence_ids: list[str] | None = None,
    fallback_reason: str | None = None,
) -> dict[str, Any]:
    timestamp = datetime.now(timezone.utc).isoformat()
    return {
        "id": f"trace-{name}",
        "name": name,
        "type": "tool",
        "status": status,
        "summary": summary,
        "timestamp": timestamp,
        "startedAt": timestamp,
        "endedAt": timestamp,
        "durationMs": 0,
        "sourceIds": source_ids or [],
        "evidenceIds": evidence_ids or [],
        "fallbackReason": fallback_reason,
        "awsMapping": {
            "service": "future AWS observability",
            "spanName": AWS_TRACE_MAPPING.get(name, f"CloudWatch span: tool.{name}"),
        },
        "output": output,
    }


def normalize_request(request: dict[str, Any]) -> dict[str, Any]:
    return {
        "siteName": request.get("siteName") or "Demo rural field fixture",
        "latitude": float(request.get("latitude", 52.2053)),
        "longitude": float(request.get("longitude", -1.6022)),
        "goal": request.get("goal") or "Pre-visit RAMS scoping pack",
        "includePlanningFixture": bool(request.get("includePlanningFixture", True)),
        "simulateMapFailure": bool(request.get("simulateMapFailure")),
        "additionalRequest": request.get("additionalRequest") or "",
    }


def source_register(include_planning_fixture: bool, simulate_map_failure: bool) -> list[dict[str, Any]]:
    sources = [
        {
            "id": "user-request",
            "label": "Submitted coordinate and options",
            "kind": "request",
            "status": "real",
            "origin": "Browser form payload",
            "trustBoundary": "User input",
            "awsMapping": "DynamoDB run record",
        },
        {
            "id": "location-fixture",
            "label": "Synthetic local authority fixture",
            "kind": "location",
            "status": "mocked",
            "origin": "backend deterministic defaults",
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
        {
            "id": "cesium-local",
            "label": "Local Cesium scene configuration",
            "kind": "3d_scene",
            "status": "real",
            "origin": "Frontend CesiumJS with backend scene config",
            "trustBoundary": "Browser rendering",
            "awsMapping": "CloudFront/static frontend plus App Runner/API Gateway backend",
        },
        {
            "id": "bedrock-future",
            "label": "Future Bedrock extraction and briefing adapter",
            "kind": "llm_adapter",
            "status": "future",
            "origin": "Not live in Demo1",
            "trustBoundary": "Future AWS account boundary",
            "awsMapping": "Amazon Bedrock model/tool planning",
        },
    ]
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


def resolve_location(request: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    latitude = float(request.get("latitude", 52.2053))
    longitude = float(request.get("longitude", -1.6022))
    location = {
        "label": request.get("siteName") or "Demo rural field fixture",
        "latitude": latitude,
        "longitude": longitude,
        "authority": "Syntheticshire District Council",
        "coordinate_system": "WGS84",
        "confidence": "high" if request.get("latitude") and request.get("longitude") else "medium",
    }
    return location, trace_step(
        "resolve_location",
        "ok",
        "Resolved the submitted coordinate to the public-safe demo location fixture.",
        {"location": location},
        source_ids=["user-request", "location-fixture"],
    )


def load_geospatial_features(location: dict[str, Any], simulate_failure: bool = False) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if simulate_failure:
        features = load_json("geospatial_features.json")["fallback_features"]
        return features, trace_step(
            "load_geospatial_features",
            "fallback",
            "Live 3D/map provider was unavailable; loaded local fallback geospatial fixture.",
            {"feature_count": len(features), "source": "fixtures/geospatial_features.json"},
            source_ids=["geo-fallback"],
            evidence_ids=["geo-fixture"],
            fallback_reason="Fallback used after simulated live map provider failure for demo testing.",
        )

    features = load_json("geospatial_features.json")["features"]
    return features, trace_step(
        "load_geospatial_features",
        "ok",
        "Loaded mock geospatial features around the coordinate.",
        {"feature_count": len(features), "source": "fixtures/geospatial_features.json"},
        source_ids=["geo-fixture"],
        evidence_ids=["geo-fixture"],
    )


def build_scene_config(location: dict[str, Any], features: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    geo_source_id = "geo-fallback" if any(feature["id"].startswith("fallback") for feature in features) else "geo-fixture"
    scene = {
        "provider": "cesium-local-fixture",
        "center": {
            "latitude": location["latitude"],
            "longitude": location["longitude"],
            "heightMeters": 260,
        },
        "camera": {
            "headingDegrees": 25,
            "pitchDegrees": -42,
            "rangeMeters": 1800,
        },
        "terrain": "ellipsoid fallback",
        "featureCount": len(features),
        "note": "No Google Maps, Google Earth, or Cesium ion key is required for Demo1.",
    }
    return scene, trace_step(
        "build_scene_config",
        "ok",
        "Created a 3D scene configuration from the resolved coordinate and feature fixture.",
        {"scene": scene},
        source_ids=["location-fixture", geo_source_id],
    )


def load_planning_context(include_planning_fixture: bool) -> tuple[str | None, dict[str, Any]]:
    if not include_planning_fixture:
        return None, trace_step(
            "load_planning_context",
            "warning",
            "Planning fixture was disabled; briefing will only use geospatial context.",
            {"source": None},
            source_ids=["planning-fixture"],
        )

    text = load_text("planning_report.txt")
    return text, trace_step(
        "load_planning_context",
        "ok",
        "Loaded synthetic planning-document fixture for hazard extraction.",
        {"source": "fixtures/planning_report.txt", "characters": len(text)},
        source_ids=["planning-fixture"],
        evidence_ids=["planning-fixture"],
    )


def extract_hazard_notes(planning_text: str | None, features: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    hazards: list[dict[str, Any]] = []
    geo_source_id = "geo-fallback" if any(feature["id"].startswith("fallback") for feature in features) else "geo-fixture"

    for feature in features:
        if feature["type"] in {"watercourse", "slope", "access_track", "bridge"}:
            hazards.append(
                {
                    "id": f"geo-{feature['id']}",
                    "title": feature["label"],
                    "category": feature["type"],
                    "source": "geospatial fixture",
                    "confidence": feature.get("confidence", "medium"),
                    "note": feature["risk_note"],
                }
            )

    if planning_text:
        planning_hazards = [
            ("flood", "Flood Risk", "Planning fixture flags watercourse proximity and seasonal surface water risk."),
            ("noise", "Noise Control", "Planning fixture expects construction traffic and plant noise limits."),
            ("heritage", "Heritage Check", "Planning fixture flags a nearby non-designated heritage asset."),
            ("uxo", "UXO Screening", "Planning fixture recommends desktop UXO screening before intrusive works."),
        ]
        lowered = planning_text.lower()
        for keyword, title, note in planning_hazards:
            if keyword in lowered:
                hazards.append(
                    {
                        "id": f"planning-{keyword}",
                        "title": title,
                        "category": keyword,
                        "source": "synthetic planning fixture",
                        "confidence": "medium",
                        "note": note,
                    }
                )

    return hazards, trace_step(
        "extract_hazard_notes",
        "ok" if hazards else "warning",
        "Extracted hazard notes from deterministic rules over fixture data.",
        {"hazard_count": len(hazards)},
        source_ids=[geo_source_id, "planning-fixture"],
        evidence_ids=["geo-fixture", "planning-fixture"] if planning_text else ["geo-fixture"],
    )


def create_annotations(location: dict[str, Any], hazards: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    offsets = [
        (0.0020, -0.0015),
        (-0.0015, 0.0017),
        (0.0012, 0.0022),
        (-0.0023, -0.0010),
        (0.0007, -0.0022),
        (-0.0004, 0.0026),
    ]
    annotations = []
    for index, hazard in enumerate(hazards[:8]):
        lat_offset, lon_offset = offsets[index % len(offsets)]
        annotations.append(
            {
                "id": hazard["id"],
                "title": hazard["title"],
                "category": hazard["category"],
                "latitude": round(location["latitude"] + lat_offset, 6),
                "longitude": round(location["longitude"] + lon_offset, 6),
                "confidence": hazard["confidence"],
                "note": hazard["note"],
            }
        )

    return annotations, trace_step(
        "create_annotations",
        "ok",
        "Converted hazards into 3D map annotations with fixture offsets.",
        {"annotation_count": len(annotations)},
        evidence_ids=[hazard["id"] for hazard in hazards[:8]],
    )


def generate_site_brief(
    location: dict[str, Any],
    hazards: list[dict[str, Any]],
    planning_text: str | None,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    evidence = [
        {
            "id": "geo-fixture",
            "title": "Mock geospatial feature pack",
            "source": "fixtures/geospatial_features.json",
            "status": "mocked",
            "why_it_matters": "Provides watercourse, slope, access, bridge, and imagery-derived features for Demo1.",
        }
    ]
    if planning_text:
        evidence.append(
            {
                "id": "planning-fixture",
                "title": "Synthetic nearby planning report extract",
                "source": "fixtures/planning_report.txt",
                "status": "mocked",
                "why_it_matters": "Lets the agent demonstrate planning-document hazard extraction without scraping a live LPA portal.",
            }
        )

    limitations = [
        "Demo1 uses synthetic fixtures and must not be treated as certified RAMS.",
        "All hazards need competent human review and current source checks before site work.",
        "Imagery-derived or inferred features are labelled low confidence.",
    ]
    if not planning_text:
        limitations.append("Planning evidence was unavailable, so document-derived hazards may be missing.")

    briefing = {
        "site": location["label"],
        "headline": "Pre-visit 3D field briefing for early RAMS scoping.",
        "summary": [
            f"Coordinate resolved to {location['latitude']}, {location['longitude']} in the demo authority fixture.",
            f"{len(hazards)} candidate hazards were found from geospatial and planning fixtures.",
            "The output is a review pack, not operational approval.",
        ],
        "priority_checks": [hazard["title"] for hazard in hazards[:5]],
        "before_site_visit": [
            "Verify access route, gate width, bridge limits, and parking area.",
            "Confirm flood risk and ground conditions with current official sources.",
            "Escalate heritage, UXO, ecology, or aggressive-animal concerns to competent reviewers.",
        ],
        "limitations": limitations,
    }

    return briefing, evidence, trace_step(
        "generate_site_brief",
        "ok",
        "Generated a RAMS-style briefing with explicit limitations and evidence references.",
        {"evidence_count": len(evidence), "priority_checks": len(briefing["priority_checks"])},
        evidence_ids=[item["id"] for item in evidence],
    )


def safety_gate(request: dict[str, Any], briefing: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    user_text = " ".join(
        str(request.get(key, ""))
        for key in ("goal", "useCase", "additionalRequest")
    ).lower()
    blocked_terms = [
        "certified rams",
        "certify rams",
        "emergency route",
        "guarantee safe",
        "approve work",
        "replace competent",
    ]
    blocked = any(term in user_text for term in blocked_terms)
    decision = {
        "allowed": not blocked,
        "level": "blocked" if blocked else "review_required",
        "message": (
            "Blocked: this demo cannot certify RAMS, approve work, or provide emergency guidance."
            if blocked
            else "Allowed as a non-certified pre-visit briefing that requires human review."
        ),
        "triggeredRules": [term for term in blocked_terms if term in user_text],
        "requiresHumanReview": True,
        "decisionId": "safety-demo1-blocked" if blocked else "safety-demo1-review-required",
    }
    if blocked:
        briefing["headline"] = "Request blocked by safety gate."
        briefing["summary"] = [decision["message"]]
        briefing["priority_checks"] = []

    return decision, trace_step(
        "safety_gate",
        "blocked" if blocked else "ok",
        decision["message"],
        {
            "allowed": decision["allowed"],
            "level": decision["level"],
            "triggeredRules": decision["triggeredRules"],
        },
        evidence_ids=["safety-policy"],
    )


def architecture_snapshot(
    trace: list[dict[str, Any]],
    request_summary: dict[str, Any],
    sources: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
    safety: dict[str, Any],
) -> dict[str, Any]:
    return {
        "runOverview": {
            "siteName": request_summary["siteName"],
            "goal": request_summary["goal"],
            "coordinate": f"{request_summary['latitude']}, {request_summary['longitude']}",
            "planningFixture": "enabled" if request_summary["includePlanningFixture"] else "disabled",
            "mapMode": "fallback" if request_summary["simulateMapFailure"] else "fixture",
            "safetyLevel": safety["level"],
        },
        "nodes": [
            {"id": "ui", "label": "React/Vite UI", "boundary": "frontend"},
            {"id": "api", "label": "FastAPI run endpoint", "boundary": "backend"},
            {"id": "agent", "label": "3D-RAMS agent loop", "boundary": "backend"},
            {"id": "fixtures", "label": "Fixture data", "boundary": "mock data"},
            {"id": "aws", "label": "Future AWS path", "boundary": "production stretch"},
        ],
        "edges": [
            {"from": "ui", "to": "api", "label": "POST /api/run"},
            {"from": "api", "to": "agent", "label": "validated request"},
            {"from": "agent", "to": "fixtures", "label": "tool calls"},
            {"from": "agent", "to": "ui", "label": "scene, evidence, trace"},
            {"from": "agent", "to": "aws", "label": "Bedrock, DynamoDB, S3, CloudWatch later"},
        ],
        "currentTrace": [
            {
                "id": step["id"],
                "name": step["name"],
                "status": step["status"],
                "summary": step["summary"],
                "durationMs": step["durationMs"],
                "sourceIds": step["sourceIds"],
                "evidenceIds": step["evidenceIds"],
                "fallbackReason": step["fallbackReason"],
            }
            for step in trace
        ],
        "sources": sources,
        "evidenceFlow": [
            {
                "id": item["id"],
                "title": item["title"],
                "status": item["status"],
                "feeds": ["annotations", "briefing", "trace"],
            }
            for item in evidence
        ],
        "safetyGate": {
            "allowed": safety["allowed"],
            "level": safety["level"],
            "message": safety["message"],
            "triggeredRules": safety["triggeredRules"],
            "requiresHumanReview": safety["requiresHumanReview"],
            "awsMapping": "Future Bedrock Guardrails plus human approval queue",
        },
        "awsPath": [
            {"local": "Deterministic Python agent loop", "future": "Bedrock model/tool planning"},
            {"local": "JSON trace in API response", "future": "CloudWatch logs, metrics, traces"},
            {"local": "Evidence list in response", "future": "S3 evidence pack"},
            {"local": "Per-request in-memory run", "future": "DynamoDB run/session record"},
            {"local": "Rule-based safety gate", "future": "Guardrails plus human review"},
        ],
        "realVsMocked": [
            {"component": "Agent workflow", "status": "real deterministic code"},
            {"component": "3D viewer", "status": "real local Cesium scene"},
            {"component": "Planning documents", "status": "synthetic fixture"},
            {"component": "Live Google 3D / Earth", "status": "not used in Demo1"},
            {"component": "AWS Bedrock / CloudWatch", "status": "designed, not required for Demo1"},
        ],
    }
