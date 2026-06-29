from __future__ import annotations

from typing import Any

from .config import RuntimeConfig
from .fixtures import load_fixture_pack
from .tools import (
    apply_bedrock_briefing,
    architecture_snapshot,
    build_scene_config,
    create_annotations,
    extract_hazard_notes,
    generate_site_brief,
    load_geospatial_features,
    load_planning_context,
    normalize_request,
    resolve_location,
    safety_gate,
    source_register,
    trace_step,
)


def run_site_briefing(request: dict[str, Any] | None = None) -> dict[str, Any]:
    request = request or {}
    upstream_context = request.get("agentcoreUpstream")
    request_summary = normalize_request(request)
    fixture_pack, fixture_pack_warning = load_fixture_pack(request_summary["fixturePack"])
    if fixture_pack:
        pack_location = fixture_pack["location"]
        request_summary["fixturePack"] = fixture_pack["name"]
        request_summary["siteName"] = pack_location["label"]
        request_summary["latitude"] = float(pack_location["latitude"])
        request_summary["longitude"] = float(pack_location["longitude"])

    config = RuntimeConfig.from_env(request_bedrock=request_summary["useBedrock"])
    trace: list[dict[str, Any]] = []

    if fixture_pack_warning:
        trace.append(
            trace_step(
                "load_fixture_pack",
                "fallback",
                fixture_pack_warning["reason"],
                fixture_pack_warning,
                fallback_reason=fixture_pack_warning["reason"],
            )
        )

    location, step = resolve_location(request, fixture_pack=fixture_pack)
    trace.append(step)

    features, step = load_geospatial_features(
        location,
        simulate_failure=bool(request.get("simulateMapFailure")),
        fixture_pack=fixture_pack,
    )
    trace.append(step)

    scene, step = build_scene_config(location, features, fixture_pack=fixture_pack)
    trace.append(step)

    planning_text, step = load_planning_context(
        include_planning_fixture=bool(request.get("includePlanningFixture", True)),
        fixture_pack=fixture_pack,
    )
    trace.append(step)

    hazards, step = extract_hazard_notes(planning_text, features, fixture_pack=fixture_pack)
    trace.append(step)

    annotations, step = create_annotations(location, hazards)
    trace.append(step)

    briefing, evidence, step = generate_site_brief(location, hazards, planning_text, fixture_pack=fixture_pack)
    trace.append(step)

    briefing, step, bedrock_status, bedrock_fallback_reason = apply_bedrock_briefing(
        config,
        location,
        hazards,
        briefing,
        evidence,
        planning_text,
    )
    trace.append(step)

    safety, step = safety_gate(request, briefing)
    trace.append(step)

    sources = source_register(
        include_planning_fixture=request_summary["includePlanningFixture"],
        simulate_map_failure=request_summary["simulateMapFailure"],
        bedrock_status=bedrock_status,
        config=config,
        fixture_pack=fixture_pack,
    )
    runtime = config.public_runtime(status=bedrock_status, fallback_reason=bedrock_fallback_reason)
    runtime["fixturePack"] = fixture_pack["name"] if fixture_pack else None
    runtime["fixturePackMode"] = "cached-public-fixture" if fixture_pack else "synthetic-default"
    runtime["liveApiCalls"] = False

    return {
        "runId": "demo1-local-run",
        "upstream": upstream_context,
        "request": request_summary,
        "runtime": runtime,
        "location": location,
        "scene": scene,
        "hazards": hazards if safety["allowed"] else [],
        "annotations": annotations if safety["allowed"] else [],
        "briefing": briefing,
        "evidence": evidence,
        "sources": sources,
        "safety": safety,
        "trace": trace,
        "architecture": architecture_snapshot(trace, request_summary, sources, evidence, safety, runtime),
    }
