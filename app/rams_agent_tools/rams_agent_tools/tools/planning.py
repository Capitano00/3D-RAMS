from __future__ import annotations

from typing import Any

from ..fixtures import load_text
from .telemetry import trace_step


def load_planning_context(
    include_planning_fixture: bool,
    fixture_pack: dict[str, Any] | None = None,
) -> tuple[str | None, dict[str, Any]]:
    if fixture_pack:
        planning = fixture_pack.get("planning", {})
        source_ids = planning.get("source_ids", [])
        if not include_planning_fixture:
            return None, trace_step(
                "load_planning_context",
                "warning",
                "Planning fixture was disabled; cached pack briefing will only use geospatial context.",
                {"source": None, "fixturePack": fixture_pack["name"], "dataMode": "cached-public-fixture"},
                source_ids=source_ids,
            )

        text = planning.get("text")
        if not text:
            return None, trace_step(
                "load_planning_context",
                "warning",
                "Cached fixture pack did not include planning text; briefing will only use geospatial context.",
                {"source": planning.get("file"), "fixturePack": fixture_pack["name"]},
                source_ids=source_ids,
                fallback_reason="Planning text was missing from the selected cached fixture pack.",
            )

        return text, trace_step(
            "load_planning_context",
            "ok",
            "Loaded cached public planning/context notes from fixture pack.",
            {
                "source": f"fixtures/{fixture_pack['name']}/{planning.get('file')}",
                "characters": len(text),
                "fixturePack": fixture_pack["name"],
                "dataMode": "cached-public-fixture",
            },
            source_ids=source_ids,
            evidence_ids=planning.get("evidence_ids", source_ids),
        )

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
