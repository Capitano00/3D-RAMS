from __future__ import annotations

from typing import Any

from .telemetry import trace_step


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
                "sourceIds": hazard.get("sourceIds", []),
                "evidenceIds": hazard.get("evidenceIds", []),
            }
        )

    return annotations, trace_step(
        "create_annotations",
        "ok",
        "Converted hazards into 3D map annotations with fixture offsets.",
        {"annotation_count": len(annotations)},
        evidence_ids=[hazard["id"] for hazard in hazards[:8]],
    )
