from __future__ import annotations

from typing import Any

from ..fixtures import load_json
from .telemetry import trace_step


def resolve_location(
    request: dict[str, Any],
    fixture_pack: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if fixture_pack:
        pack_location = fixture_pack["location"]
        location = {
            "label": pack_location["label"],
            "latitude": float(pack_location["latitude"]),
            "longitude": float(pack_location["longitude"]),
            "authority": pack_location.get("authority", "Unknown public authority"),
            "coordinate_system": pack_location.get("coordinate_system", "WGS84"),
            "confidence": pack_location.get("confidence", "medium"),
            "fixturePack": fixture_pack["name"],
            "dataMode": "cached-public-fixture",
            "sourceIds": pack_location.get("source_ids", []),
        }
        return location, trace_step(
            "resolve_location",
            "ok",
            "Loaded cached public fixture-pack location metadata.",
            {"location": location, "fixturePack": fixture_pack["name"], "dataMode": "cached-public-fixture"},
            source_ids=["user-request", *pack_location.get("source_ids", [])],
        )

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
        {"location": location, "dataMode": "synthetic-fixture"},
        source_ids=["user-request", "location-fixture"],
    )


def load_geospatial_features(
    location: dict[str, Any],
    simulate_failure: bool = False,
    fixture_pack: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
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

    if fixture_pack:
        geospatial = fixture_pack.get("geospatial", {})
        features = geospatial.get("features", [])
        source_ids = geospatial.get("source_ids", [])
        evidence_ids = geospatial.get("evidence_ids", source_ids)
        return features, trace_step(
            "load_geospatial_features",
            "ok",
            "Loaded cached public geospatial feature pack without live API calls.",
            {
                "feature_count": len(features),
                "fixturePack": fixture_pack["name"],
                "dataMode": "cached-public-fixture",
                "sourceIds": source_ids,
            },
            source_ids=source_ids,
            evidence_ids=evidence_ids,
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


def build_scene_config(
    location: dict[str, Any],
    features: list[dict[str, Any]],
    fixture_pack: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    uses_geo_fallback = any(feature["id"].startswith("fallback") for feature in features)
    geo_source_ids = (
        ["geo-fallback"]
        if uses_geo_fallback
        else (
            fixture_pack.get("geospatial", {}).get("source_ids", [])
            if fixture_pack
            else ["geo-fixture"]
        )
    )
    scene = {
        "provider": "cesium-local-cached-fixture" if fixture_pack else "cesium-local-fixture",
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
        "fixturePack": fixture_pack["name"] if fixture_pack else None,
        "dataMode": "cached-public-fixture" if fixture_pack else "synthetic-fixture",
        "note": "No Google Maps, Google Earth, Cesium ion key, or live geospatial API is required for Demo1.",
    }
    return scene, trace_step(
        "build_scene_config",
        "ok",
        "Created a 3D scene configuration from the resolved coordinate and feature fixture.",
        {"scene": scene},
        source_ids=[*location.get("sourceIds", ["location-fixture"]), *geo_source_ids],
    )
