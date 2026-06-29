from __future__ import annotations

from typing import Any

from ..bedrock_adapter import BedrockAdapterError, generate_bedrock_briefing
from ..config import RuntimeConfig
from .telemetry import trace_step


def generate_site_brief(
    location: dict[str, Any],
    hazards: list[dict[str, Any]],
    planning_text: str | None,
    fixture_pack: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    if fixture_pack:
        evidence = fixture_pack.get("evidence", [])
        limitations = [
            "This cached pack is public-safe demo evidence and is not live, exhaustive, or operational advice.",
            "The briefing is not certified RAMS, not emergency guidance, and not work approval.",
            "All hazards need competent human review and current source checks before site work.",
            "Imagery-derived or inferred features are labelled low confidence.",
        ]
        if not planning_text:
            limitations.append("Planning/context notes were unavailable or disabled, so document-derived hazards may be missing.")

        briefing = {
            "site": location["label"],
            "headline": "Cached public-source review pack for early site scoping.",
            "summary": [
                f"Loaded fixture pack '{fixture_pack['name']}' with cached public-source metadata.",
                f"{len(hazards)} candidate hazards were found from cached geospatial and planning/context evidence.",
                "The output is a review pack. It is not certified RAMS and not work approval.",
            ],
            "priority_checks": [hazard["title"] for hazard in hazards[:5]],
            "before_site_visit": [
                "Check current official flood, planning, access, and highway sources before relying on this pack.",
                "Confirm river-edge, bridge, access, and public-realm constraints with a competent reviewer.",
                "Record source age and confidence before escalating any claim into a RAMS workflow.",
            ],
            "limitations": limitations,
            "fixturePack": fixture_pack["name"],
            "dataMode": "cached-public-fixture",
        }

        return briefing, evidence, trace_step(
            "generate_site_brief",
            "ok",
            "Generated deterministic briefing from cached fixture-pack evidence with explicit limitations.",
            {
                "mode": "deterministic",
                "fixturePack": fixture_pack["name"],
                "dataMode": "cached-public-fixture",
                "evidence_count": len(evidence),
                "priority_checks": len(briefing["priority_checks"]),
            },
            source_ids=sorted({source_id for item in evidence for source_id in item.get("sourceIds", [])}),
            evidence_ids=[item["id"] for item in evidence],
        )

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
        "Generated deterministic fallback briefing with explicit limitations and evidence references.",
        {
            "mode": "deterministic",
            "evidence_count": len(evidence),
            "priority_checks": len(briefing["priority_checks"]),
        },
        evidence_ids=[item["id"] for item in evidence],
    )


def apply_bedrock_briefing(
    config: RuntimeConfig,
    location: dict[str, Any],
    hazards: list[dict[str, Any]],
    briefing: dict[str, Any],
    evidence: list[dict[str, Any]],
    planning_text: str | None,
) -> tuple[dict[str, Any], dict[str, Any], str, str | None]:
    if not config.bedrock_requested:
        return briefing, trace_step(
            "generate_bedrock_briefing",
            "disabled",
            "Bedrock briefing was not requested for this run; deterministic briefing remains active.",
            {"mode": "deterministic", "requested": False},
            source_ids=["bedrock-briefing"],
            evidence_ids=[item["id"] for item in evidence],
        ), "disabled", "Bedrock was not requested."

    if not config.bedrock_enabled:
        return briefing, trace_step(
            "generate_bedrock_briefing",
            "disabled",
            "Bedrock briefing is disabled by environment; deterministic briefing remains active.",
            {
                "mode": "deterministic",
                "requested": True,
                "enabled": False,
                "modelId": None,
                "maxTokens": None,
                "temperature": None,
            },
            source_ids=["bedrock-briefing"],
            evidence_ids=[item["id"] for item in evidence],
            fallback_reason="Set ENABLE_BEDROCK=true with AWS credentials to use the live Bedrock path.",
        ), "disabled", "ENABLE_BEDROCK is not true."

    try:
        bedrock_briefing, metadata = generate_bedrock_briefing(
            config=config,
            location=location,
            hazards=hazards,
            deterministic_briefing=briefing,
            evidence=evidence,
            planning_available=planning_text is not None,
        )
    except (BedrockAdapterError, Exception) as exc:
        fallback_reason = f"Bedrock briefing failed; deterministic briefing used. Reason: {exc}"
        return briefing, trace_step(
            "generate_bedrock_briefing",
            "fallback",
            "Bedrock briefing failed; deterministic briefing remains active.",
            {
                "mode": "deterministic-fallback",
                "modelId": config.bedrock_model_id,
                "awsRegion": config.aws_region,
                "maxTokens": config.bedrock_max_tokens,
                "temperature": config.bedrock_temperature,
                "errorType": exc.__class__.__name__,
            },
            source_ids=["bedrock-briefing"],
            evidence_ids=[item["id"] for item in evidence],
            fallback_reason=fallback_reason,
        ), "fallback", fallback_reason

    bedrock_status = "mocked" if metadata.get("mode") == "bedrock-mock" else "real"
    return bedrock_briefing, trace_step(
        "generate_bedrock_briefing",
        "ok",
        "Generated one Bedrock-backed briefing from structured hazards and evidence.",
        metadata,
        source_ids=["bedrock-briefing"],
        evidence_ids=[item["id"] for item in evidence],
        duration_ms=int(metadata.get("latencyMs", 0)),
    ), bedrock_status, None
