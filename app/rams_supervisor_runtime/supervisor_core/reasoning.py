from __future__ import annotations

from typing import Any

from rams_agent_tools.tools import trace_step


def reason_over_evidence(
    *,
    request: dict[str, Any],
    location: dict[str, Any],
    hazards: list[dict[str, Any]],
    annotations: list[dict[str, Any]],
    briefing: dict[str, Any],
    evidence: list[dict[str, Any]],
    sources: list[dict[str, Any]],
    safety: dict[str, Any],
    external_signals: dict[str, Any] | None = None,
    material_ingestion: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Produce an inspectable reasoning artifact without exposing hidden reasoning."""
    open_web = (external_signals or {}).get("openWeb") or {"status": "not_configured", "items": []}
    material_ingestion = material_ingestion or {"status": "disabled", "accepted": 0, "skipped": []}
    safety_allowed = bool(safety.get("allowed"))
    source_ids = _source_ids(sources)
    evidence_ids = _evidence_ids(evidence)

    report_fit = [
        _section_fit(
            section_id="location-context",
            status="supported" if location else "missing",
            rationale=(
                "Resolved site location is available for the review pack."
                if location
                else "No resolved site location is available."
            ),
            source_ids=_present(_strings(location.get("sourceIds"))),
            evidence_ids=[],
            confidence=str(location.get("confidence") or ("medium" if location else "low")),
        ),
        _section_fit(
            section_id="spatial-context",
            status="supported" if annotations and safety_allowed else "partial",
            rationale=(
                "3D annotations are available for the frontend visualization."
                if annotations and safety_allowed
                else "Spatial context exists, but annotations are withheld or incomplete."
            ),
            source_ids=_sources_matching(source_ids, ["geospatial", "osm", "flood"]),
            evidence_ids=[],
            confidence="medium" if annotations and safety_allowed else "low",
        ),
        _section_fit(
            section_id="planning-context",
            status="supported" if _has_available_source(sources, "planning") else "partial",
            rationale=(
                "Planning/context source metadata is available for report caveats."
                if _has_available_source(sources, "planning")
                else "Planning/context data was unavailable or disabled in this run."
            ),
            source_ids=_sources_matching(source_ids, ["planning"]),
            evidence_ids=[],
            confidence="medium" if _has_available_source(sources, "planning") else "low",
        ),
        _section_fit(
            section_id="candidate-findings",
            status="supported" if hazards and safety_allowed else "partial",
            rationale=(
                "Candidate findings have linked evidence and remain inside the safety boundary."
                if hazards and safety_allowed
                else "Candidate findings are unavailable or blocked by the safety boundary."
            ),
            source_ids=_dedupe([sid for hazard in hazards for sid in _strings(hazard.get("sourceIds"))]),
            evidence_ids=_dedupe([eid for hazard in hazards for eid in _strings(hazard.get("evidenceIds"))]),
            confidence="medium" if hazards and safety_allowed else "low",
        ),
        _section_fit(
            section_id="user-materials",
            status="supported" if material_ingestion.get("accepted") else "missing",
            rationale=(
                "Authorized ASI/ASI:ONE material references produced safe evidence summaries."
                if material_ingestion.get("accepted")
                else "No authorized material-derived evidence was available for this run."
            ),
            source_ids=_strings(material_ingestion.get("sourceIds")),
            evidence_ids=_strings(material_ingestion.get("evidenceIds")),
            confidence="medium" if material_ingestion.get("accepted") else "low",
        ),
        _section_fit(
            section_id="open-web-signals",
            status="supported" if open_web.get("items") else "missing",
            rationale=(
                "Open-web signals were returned and should be treated as non-authoritative context."
                if open_web.get("items")
                else "Open-web/Tavily signals were not configured or returned no usable items."
            ),
            source_ids=[],
            evidence_ids=[],
            confidence="low",
        ),
        _section_fit(
            section_id="review-boundary",
            status="supported" if safety_allowed else "conflict",
            rationale=str(safety.get("message") or "Safety review result is unavailable."),
            source_ids=[],
            evidence_ids=["safety-policy"],
            confidence="high",
        ),
    ]

    finding_assessments = [
        _finding_assessment(hazard, safety_allowed=safety_allowed)
        for hazard in hazards
    ]

    gaps = _data_gaps(
        request=request,
        briefing=briefing,
        sources=sources,
        open_web=open_web,
        material_ingestion=material_ingestion,
    )
    conflicts = []
    if not safety_allowed:
        conflicts.append(
            {
                "id": "safety-boundary",
                "severity": "high",
                "message": str(safety.get("message") or "Safety boundary blocked the generated output."),
                "sourceIds": [],
                "evidenceIds": ["safety-policy"],
            }
        )

    reasoning = {
        "mode": "deterministic",
        "status": "warning" if gaps or conflicts else "ok",
        "summary": _summary(safety_allowed=safety_allowed, hazards=hazards, gaps=gaps, open_web=open_web),
        "reportFit": report_fit,
        "findingAssessments": finding_assessments,
        "gaps": gaps,
        "conflicts": conflicts,
        "reviewQuestions": _review_questions(gaps=gaps, open_web=open_web),
    }

    return {
        "reasoning": reasoning,
        "trace": trace_step(
            "reason_over_evidence",
            "warning" if reasoning["status"] == "warning" else "ok",
            reasoning["summary"],
            {
                "mode": reasoning["mode"],
                "status": reasoning["status"],
                "reportFitCount": len(report_fit),
                "findingAssessmentCount": len(finding_assessments),
                "gapCount": len(gaps),
                "conflictCount": len(conflicts),
                "openWebStatus": open_web.get("status"),
                "materialIngestionStatus": material_ingestion.get("status"),
                "materialAccepted": material_ingestion.get("accepted"),
                "materialSkipped": material_ingestion.get("skippedCount"),
            },
            source_ids=source_ids,
            evidence_ids=evidence_ids,
        ),
    }


def _section_fit(
    *,
    section_id: str,
    status: str,
    rationale: str,
    source_ids: list[str],
    evidence_ids: list[str],
    confidence: str,
) -> dict[str, Any]:
    return {
        "sectionId": section_id,
        "status": status,
        "rationale": rationale,
        "sourceIds": source_ids,
        "evidenceIds": evidence_ids,
        "confidence": confidence,
    }


def _finding_assessment(hazard: dict[str, Any], *, safety_allowed: bool) -> dict[str, Any]:
    finding_id = str(hazard.get("id") or "unknown-finding")
    source_ids = _strings(hazard.get("sourceIds"))
    evidence_ids = _strings(hazard.get("evidenceIds"))
    supported = bool(source_ids or evidence_ids)
    if not safety_allowed:
        decision = "exclude"
        rationale = "Finding is withheld because the safety gate blocked the generated output."
    elif supported:
        decision = "include_with_caveat"
        rationale = "Finding has source or evidence references and remains subject to human review."
    else:
        decision = "needs_review"
        rationale = "Finding lacks explicit source or evidence references."
    return {
        "findingId": finding_id,
        "decision": decision,
        "rationale": rationale,
        "sourceIds": source_ids,
        "evidenceIds": evidence_ids,
        "confidence": str(hazard.get("confidence") or ("medium" if supported else "low")),
        "humanReviewRequired": True,
    }


def _data_gaps(
    *,
    request: dict[str, Any],
    briefing: dict[str, Any],
    sources: list[dict[str, Any]],
    open_web: dict[str, Any],
    material_ingestion: dict[str, Any],
) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []
    if not _has_available_source(sources, "planning"):
        gaps.append(
            {
                "id": "planning-context",
                "severity": "medium",
                "message": "Planning/context data was unavailable, disabled, or fixture-only.",
                "affectsSections": ["planning-context"],
            }
        )
    if open_web.get("status") in {None, "not_configured", "disabled"} or not open_web.get("items"):
        gaps.append(
            {
                "id": "open-web-signals",
                "severity": "low",
                "message": "Open-web signals were not available for this run.",
                "affectsSections": ["open-web-signals"],
            }
        )
    if not material_ingestion.get("accepted"):
        gaps.append(
            {
                "id": "user-materials",
                "severity": "low",
                "message": "No authorized material-derived evidence was available for this run.",
                "affectsSections": ["user-materials", "candidate-findings"],
            }
        )
    for skipped in material_ingestion.get("skipped") or []:
        if not isinstance(skipped, dict):
            continue
        material_label = skipped.get("label") or skipped.get("materialId") or "material reference"
        gaps.append(
            {
                "id": f"material-{skipped.get('reason', 'skipped')}",
                "severity": "medium",
                "message": f"Material reference '{material_label}' was skipped: {skipped.get('reason')}.",
                "affectsSections": ["user-materials", "candidate-findings"],
            }
        )
    if not request.get("additionalRequest"):
        gaps.append(
            {
                "id": "user-context",
                "severity": "low",
                "message": "No additional user notes or constraints were supplied.",
                "affectsSections": ["review-boundary"],
            }
        )
    for index, limitation in enumerate(_strings(briefing.get("limitations"))):
        gaps.append(
            {
                "id": f"briefing-limitation-{index + 1}",
                "severity": "medium" if "planning" in limitation.lower() else "low",
                "message": limitation,
                "affectsSections": ["planning-context", "candidate-findings"],
            }
        )
    return _dedupe_gap_objects(gaps)


def _review_questions(*, gaps: list[dict[str, Any]], open_web: dict[str, Any]) -> list[str]:
    questions = [
        "Do source references adequately support each candidate finding?",
        "Does the report remain clearly bounded as a non-certified pre-visit review pack?",
    ]
    if gaps:
        questions.append("Which data gaps should be resolved before site visit planning?")
    if open_web.get("items"):
        questions.append("Are open-web signals current, relevant, and clearly labeled as non-authoritative?")
    else:
        questions.append("Should Tavily/open-web signals be enabled for this case?")
    return questions


def _summary(
    *,
    safety_allowed: bool,
    hazards: list[dict[str, Any]],
    gaps: list[dict[str, Any]],
    open_web: dict[str, Any],
) -> str:
    if not safety_allowed:
        return "Supervisor reasoning withheld report findings because the safety gate blocked the output."
    return (
        f"Supervisor reasoning assessed {len(hazards)} candidate findings, "
        f"{len(gaps)} data gaps, and open-web status '{open_web.get('status', 'not_configured')}'."
    )


def _has_available_source(sources: list[dict[str, Any]], token: str) -> bool:
    for source in sources:
        source_id = str(source.get("id") or "").lower()
        status = str(source.get("status") or "").lower()
        if token in source_id and status not in {"unavailable", "disabled"}:
            return True
    return False


def _source_ids(sources: list[dict[str, Any]]) -> list[str]:
    return _dedupe([str(source.get("id")) for source in sources if source.get("id")])


def _evidence_ids(evidence: list[dict[str, Any]]) -> list[str]:
    return _dedupe([str(item.get("id")) for item in evidence if item.get("id")])


def _sources_matching(source_ids: list[str], tokens: list[str]) -> list[str]:
    return [sid for sid in source_ids if any(token in sid.lower() for token in tokens)]


def _strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item)]


def _present(items: list[str]) -> list[str]:
    return [item for item in items if item]


def _dedupe(items: list[str]) -> list[str]:
    seen = set()
    output = []
    for item in items:
        if item not in seen:
            output.append(item)
            seen.add(item)
    return output


def _dedupe_gap_objects(gaps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    output = []
    for gap in gaps:
        key = (gap.get("id"), gap.get("message"))
        if key not in seen:
            output.append(gap)
            seen.add(key)
    return output
