from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen

from ..config import RuntimeConfig
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

    confirmation = request.get("locationConfirmation") if isinstance(request.get("locationConfirmation"), dict) else {}
    candidate = confirmation.get("candidate") if isinstance(confirmation.get("candidate"), dict) else {}
    source_ids = [candidate.get("sourceId") or "location-fixture"]
    data_mode = candidate.get("dataMode") if candidate else "synthetic-fixture"
    latitude = float(request.get("latitude", 52.2053))
    longitude = float(request.get("longitude", -1.6022))
    location = {
        "label": request.get("siteName") or "Demo rural field fixture",
        "latitude": latitude,
        "longitude": longitude,
        "authority": candidate.get("authority") or "Syntheticshire District Council",
        "coordinate_system": "WGS84",
        "confidence": candidate.get("confidence") or ("high" if request.get("latitude") and request.get("longitude") else "medium"),
        "dataMode": data_mode,
        "sourceIds": source_ids,
    }
    return location, trace_step(
        "resolve_location",
        "ok",
        "Resolved the confirmed location evidence for supervisor tooling.",
        {"location": location, "dataMode": data_mode, "locationConfirmation": confirmation or None},
        source_ids=["user-request", *source_ids],
    )


def load_geospatial_features(
    location: dict[str, Any],
    simulate_failure: bool = False,
    fixture_pack: dict[str, Any] | None = None,
    config: RuntimeConfig | None = None,
    location_confirmation: dict[str, Any] | None = None,
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
    planning_data = _load_live_planning_data(location, config, location_confirmation)
    live_features = planning_data.pop("features", [])
    if planning_data["status"] == "failed":
        status = "fallback"
        summary = "Live Planning Data lookup failed; loaded mock geospatial features around the coordinate."
    elif planning_data["status"] in {"live", "partial"}:
        status = "ok"
        summary = "Loaded mock geospatial features and optional live Planning Data features around the coordinate."
    else:
        status = "ok"
        summary = "Loaded mock geospatial features around the coordinate."
    all_features = [*features, *live_features]
    return all_features, trace_step(
        "load_geospatial_features",
        status,
        summary,
        {
            "feature_count": len(all_features),
            "source": "fixtures/geospatial_features.json",
            "planningData": planning_data,
        },
        source_ids=["geo-fixture", *planning_data.get("sourceIds", [])],
        evidence_ids=["geo-fixture"],
        fallback_reason=planning_data.get("fallbackReason"),
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
        "dataMode": "cached-public-fixture" if fixture_pack else location.get("dataMode") or "synthetic-fixture",
        "note": "No Google Maps, Google Earth, Cesium ion key, or live geospatial API is required for Demo1.",
    }
    return scene, trace_step(
        "build_scene_config",
        "ok",
        "Created a 3D scene configuration from the resolved coordinate and feature fixture.",
        {"scene": scene},
        source_ids=[*location.get("sourceIds", ["location-fixture"]), *geo_source_ids],
    )


def _load_live_planning_data(
    location: dict[str, Any],
    config: RuntimeConfig | None,
    location_confirmation: dict[str, Any] | None,
) -> dict[str, Any]:
    metadata = _planning_data_metadata(config)
    if not config or not config.live_planning_data_enabled:
        return {**metadata, "status": "disabled", "fallbackReason": "ENABLE_LIVE_PLANNING_DATA is not true."}
    if str((location_confirmation or {}).get("status") or "").strip().lower() != "confirmed":
        return {**metadata, "status": "skipped", "fallbackReason": "Location is not confirmed."}

    params: list[tuple[str, Any]] = [
        ("latitude", location["latitude"]),
        ("longitude", location["longitude"]),
        ("limit", config.planning_data_result_limit),
    ]
    params.extend(("dataset", dataset) for dataset in config.planning_data_datasets)
    url = f"{config.planning_data_endpoint}?{urlencode(params)}"
    try:
        with urlopen(url, timeout=config.planning_data_timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        return {
            **metadata,
            "status": "failed",
            "dataMode": "live-planning-data-failed",
            "liveCallAttempted": True,
            "fallbackReason": f"{type(exc).__name__}: {exc}",
        }

    entities = payload.get("entities") if isinstance(payload, dict) else []
    entities = entities if isinstance(entities, list) else []
    live_features = [
        _planning_entity_feature(entity, location)
        for entity in entities[: config.planning_data_result_limit]
        if isinstance(entity, dict)
    ]
    live_features = [feature for feature in live_features if feature]
    total = _int_or(payload.get("count"), len(live_features)) if isinstance(payload, dict) else len(live_features)
    status = "partial" if total > len(live_features) else "live"
    return {
        **metadata,
        "status": status,
        "dataMode": "live-planning-data",
        "liveCallAttempted": True,
        "featureCount": len(live_features),
        "sourceIds": ["planning-data-api"],
        "freshness": datetime.now(timezone.utc).date().isoformat(),
        "fallbackReason": None,
        "features": live_features,
    }


def _planning_data_metadata(config: RuntimeConfig | None) -> dict[str, Any]:
    return {
        "provider": "planning.data.gov.uk",
        "status": "disabled",
        "dataMode": "disabled",
        "liveCallAttempted": False,
        "featureCount": 0,
        "sourceIds": [],
        "datasets": list(config.planning_data_datasets) if config else [],
        "endpoint": config.planning_data_endpoint if config else None,
        "limit": config.planning_data_result_limit if config else None,
        "timeoutSeconds": config.planning_data_timeout_seconds if config else None,
        "attribution": "Contains public sector information licensed under the Open Government Licence v3.0. Crown copyright and database right 2026. Source: Planning Data.",
        "freshness": None,
        "fallbackReason": None,
    }


def _planning_entity_feature(entity: dict[str, Any], location: dict[str, Any]) -> dict[str, Any]:
    entity_id = entity.get("entity") or entity.get("reference") or "unknown"
    dataset = str(entity.get("dataset") or "planning-data")
    point = _wkt_point(entity.get("point")) or {"latitude": location["latitude"], "longitude": location["longitude"]}
    return {
        "id": f"planning-data-{entity_id}",
        "label": entity.get("name") or entity.get("reference") or dataset.replace("-", " ").title(),
        "type": f"planning_data:{dataset}",
        "dataset": dataset,
        "reference": entity.get("reference"),
        "entity": entity.get("entity"),
        "geometry": entity.get("geometry"),
        "centroid": point,
        "confidence": "medium",
        "risk_note": "Live Planning Data context for human review; absence or presence is not a work approval.",
        "dataMode": "live-planning-data",
        "sourceIds": ["planning-data-api"],
        "attribution": "Contains public sector information licensed under the Open Government Licence v3.0. Crown copyright and database right 2026. Source: Planning Data.",
        "freshness": entity.get("entry-date") or entity.get("start-date"),
    }


def _wkt_point(value: Any) -> dict[str, float] | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text.upper().startswith("POINT") or "(" not in text or ")" not in text:
        return None
    inside = text[text.find("(") + 1 : text.rfind(")")]
    try:
        longitude, latitude = inside.split()
        return {"latitude": float(latitude), "longitude": float(longitude)}
    except ValueError:
        return None


def _int_or(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
