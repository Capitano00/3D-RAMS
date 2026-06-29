from __future__ import annotations

SUPERVISOR_TOOL_GROUPS = {
    "intake": [
        "normalize_request",
        "source_register",
    ],
    "geospatial_subagent": [
        "resolve_location",
        "load_geospatial_features",
        "build_scene_config",
    ],
    "planning_subagent": [
        "load_planning_context",
    ],
    "hazard_subagent": [
        "extract_hazard_notes",
        "create_annotations",
    ],
    "briefing_subagent": [
        "generate_site_brief",
        "apply_bedrock_briefing",
    ],
    "review_guardrail": [
        "safety_gate",
        "architecture_snapshot",
    ],
}


def tools_for_group(group: str) -> list[str]:
    return list(SUPERVISOR_TOOL_GROUPS.get(group, []))
