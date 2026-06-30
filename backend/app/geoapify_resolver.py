from __future__ import annotations

import os
import re
from typing import Any
from urllib.parse import urlencode

import httpx


_GEOCODE_URL = "https://api.geoapify.com/v1/geocode/search"


def resolve_geoapify_candidates(site_name: str, intent: dict[str, Any] | None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Resolve arbitrary named sites through Geoapify when explicitly enabled.

    The API key stays server-side. The caller must still require human
    confirmation before any map/evidence/review tools run.
    """

    intent = intent or {}
    if not _env_bool("ENABLE_GEOAPIFY_GEOCODING", False):
        return [], {"status": "skipped", "source": "geoapify", "reason": "Feature flag disabled."}
    api_key = os.getenv("GEOAPIFY_API_KEY")
    if not api_key:
        return [], {"status": "skipped", "source": "geoapify", "reason": "API key not configured."}

    query = _build_query(site_name, intent)
    limit = min(max(_env_int("GEOAPIFY_GEOCODING_LIMIT", 3), 1), 3)
    timeout = min(max(_env_float("GEOAPIFY_GEOCODING_TIMEOUT_SECONDS", 4.0), 1.0), 8.0)
    params = {
        "text": query,
        "filter": "countrycode:gb",
        "limit": str(limit),
        "format": "geojson",
        "apiKey": api_key,
    }
    try:
        response = httpx.get(
            f"{_GEOCODE_URL}?{urlencode(params)}",
            headers={"User-Agent": "3D-RAMS-hackathon-demo/0.1"},
            timeout=timeout,
        )
        response.raise_for_status()
        payload = response.json()
        features = payload.get("features") or []
        candidates = _features_to_candidates(features, site_name=site_name, intent=intent)
        return candidates[:limit], {
            "status": "ok" if candidates else "warning",
            "source": "geoapify/geocode/search",
            "query": _redact_query(query),
            "candidateCount": len(candidates[:limit]),
            "reason": "Geoapify returned source-labelled candidates." if candidates else "No candidates returned.",
        }
    except Exception as exc:
        return [], {
            "status": "warning",
            "source": "geoapify/geocode/search",
            "query": _redact_query(query),
            "reason": f"Lookup failed: {exc.__class__.__name__}",
        }


def _features_to_candidates(
    features: list[dict[str, Any]],
    *,
    site_name: str,
    intent: dict[str, Any],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen: set[tuple[float, float, str]] = set()
    for index, feature in enumerate(features):
        properties = feature.get("properties") or {}
        latitude, longitude = _coordinates(feature, properties)
        if latitude is None or longitude is None:
            continue
        label = properties.get("formatted") or properties.get("name") or site_name
        confidence = _confidence(properties)
        key = (round(float(latitude), 5), round(float(longitude), 5), str(label).lower())
        if key in seen:
            continue
        seen.add(key)
        candidates.append(
            {
                "candidateId": _candidate_id(properties, index),
                "name": str(label)[:140],
                "nearestTown": properties.get("city") or properties.get("town") or properties.get("village") or properties.get("municipality"),
                "nearestRoad": properties.get("street"),
                "countyOrAuthority": properties.get("county") or properties.get("state_district") or properties.get("state"),
                "postcodeArea": _postcode_area(properties.get("postcode")),
                "latitude": float(latitude),
                "longitude": float(longitude),
                "confidence": confidence,
                "source": "geoapify/geocode/search",
                "provider": "Geoapify",
                "dataMode": "source-labelled-location",
                "freshness": "live lookup at run time",
                "attribution": "Geoapify Geocoding API; display provider attribution where used.",
                "license": "Geoapify terms; underlying open-data attribution may apply.",
                "reason": "Candidate from server-side Geoapify lookup. Confirm before review tools run.",
                "fixturePack": None,
                "intent": intent,
            }
        )
    return candidates


def _build_query(site_name: str, intent: dict[str, Any]) -> str:
    parts = [site_name]
    for key in ("nearestTown", "localAuthority", "outcode"):
        value = intent.get(key)
        if value and str(value).lower() not in str(site_name).lower():
            parts.append(str(value))
    parts.append("United Kingdom")
    return ", ".join(parts)


def _coordinates(feature: dict[str, Any], properties: dict[str, Any]) -> tuple[float | None, float | None]:
    lat = properties.get("lat")
    lon = properties.get("lon")
    if lat is not None and lon is not None:
        return float(lat), float(lon)
    coordinates = (feature.get("geometry") or {}).get("coordinates") or []
    if len(coordinates) >= 2:
        return float(coordinates[1]), float(coordinates[0])
    return None, None


def _confidence(properties: dict[str, Any]) -> str:
    rank = properties.get("rank") or {}
    raw = rank.get("confidence")
    try:
        confidence = float(raw)
    except (TypeError, ValueError):
        confidence = None
    if confidence is None:
        return "medium"
    if confidence >= 0.8:
        return "high"
    if confidence >= 0.55:
        return "medium"
    return "low"


def _candidate_id(properties: dict[str, Any], index: int) -> str:
    source_id = str(properties.get("place_id") or properties.get("plus_code") or properties.get("formatted") or index)
    slug = re.sub(r"[^A-Za-z0-9]+", "-", source_id).strip("-").lower()[:60]
    return f"candidate-geoapify-{slug or index}"


def _postcode_area(postcode: Any) -> str | None:
    if not postcode:
        return None
    return str(postcode).strip().split()[0].upper()


def _redact_query(query: str) -> str:
    return query[:160]


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default
