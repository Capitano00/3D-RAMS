from __future__ import annotations

from typing import Any

from .telemetry import trace_step


def extract_hazard_notes(
    planning_text: str | None,
    features: list[dict[str, Any]],
    fixture_pack: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if fixture_pack:
        hazards = fixture_pack.get("hazards", [])
        source_ids = sorted({source_id for hazard in hazards for source_id in hazard.get("sourceIds", [])})
        evidence_ids = sorted({evidence_id for hazard in hazards for evidence_id in hazard.get("evidenceIds", [])})
        return hazards, trace_step(
            "extract_hazard_notes",
            "ok" if hazards else "warning",
            "Loaded cached public-source hazard notes from fixture pack.",
            {
                "hazard_count": len(hazards),
                "fixturePack": fixture_pack["name"],
                "dataMode": "cached-public-fixture",
            },
            source_ids=source_ids,
            evidence_ids=evidence_ids,
        )

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
                    "sourceIds": [geo_source_id],
                    "evidenceIds": ["geo-fixture"],
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
                        "sourceIds": ["planning-fixture"],
                        "evidenceIds": ["planning-fixture"],
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
