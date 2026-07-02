from __future__ import annotations

from copy import deepcopy
from typing import Any

from rams_agent_tools.tools import safety_gate, trace_step


MAX_REPAIR_ATTEMPTS = 1
REQUIRED_LIST_SECTIONS = ("summary", "priority_checks", "before_site_visit", "limitations")


def assess_report_grounding(
    *,
    location: dict[str, Any],
    hazards: list[dict[str, Any]],
    briefing: dict[str, Any],
) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []

    if not str(briefing.get("headline") or "").strip():
        issues.append(_issue("missing-headline", "briefing.headline", True))
    for field in REQUIRED_LIST_SECTIONS:
        if not _strings(briefing.get(field)):
            issues.append(_issue(f"missing-{field.replace('_', '-')}", f"briefing.{field}", True))

    site = str(briefing.get("site") or "").strip()
    expected_site = str(location.get("label") or "").strip()
    if expected_site and (not site or _norm(site) != _norm(expected_site)):
        issues.append(_issue("briefing-site-mismatch", "briefing.site", True))

    issues.extend(_priority_check_issues(briefing, hazards))

    generated_safety, _ = safety_gate({}, deepcopy(briefing))
    if generated_safety.get("triggeredSources", {}).get("generatedBriefing"):
        issues.append(_issue("unsafe-generated-briefing-wording", "briefing", True, severity="high"))

    for index, hazard in enumerate(hazards):
        if not _strings(hazard.get("sourceIds")) and not _strings(hazard.get("evidenceIds")):
            issues.append(_issue(f"unsupported-finding-{hazard.get('id') or index}", "findings", False))

    retryable = [issue for issue in issues if issue["repairable"]]
    return {
        "schemaVersion": "3d-rams.report-grounding-repair.v1",
        "status": "ok" if not issues else "needs_repair",
        "issueCount": len(issues),
        "repairableIssueCount": len(retryable),
        "unrepairableIssueCount": len(issues) - len(retryable),
        "issues": issues,
    }


def downgrade_briefing_for_review(
    *,
    briefing: dict[str, Any],
    location: dict[str, Any],
    hazards: list[dict[str, Any]],
    assessment: dict[str, Any],
) -> None:
    supported_titles = [
        str(hazard.get("title"))
        for hazard in hazards
        if hazard.get("title") and (_strings(hazard.get("sourceIds")) or _strings(hazard.get("evidenceIds")))
    ]
    briefing.clear()
    briefing.update(
        {
            "site": str(location.get("label") or "Unknown site"),
            "headline": "Review-required briefing downgraded by grounding repair.",
            "summary": [
                "Grounding checks found briefing defects before independent review.",
                f"{len(hazards)} candidate finding(s) remain available only for competent human review.",
                "This fallback is only a pre-visit review pack and does not authorize site work or urgent-response decisions.",
            ],
            "priority_checks": supported_titles[:5],
            "before_site_visit": [
                "Resolve the trace-visible grounding issues before relying on this pre-visit pack.",
                "Confirm sources, evidence references, and site context with a competent reviewer.",
            ],
            "limitations": [
                "Report grounding repair downgraded this briefing to a review-required fallback state.",
                f"{int(assessment.get('issueCount') or 0)} grounding issue(s) remain trace-visible.",
            ],
            "generation_mode": "grounding-repair-fallback",
        }
    )


def repair_metadata(assessment: dict[str, Any], *, attempt_count: int, stop_reason: str) -> dict[str, Any]:
    return {
        "schemaVersion": "3d-rams.report-grounding-repair.v1",
        "status": "ok" if assessment.get("issueCount") == 0 else "review_required",
        "repairAttemptCount": attempt_count,
        "repairStopReason": stop_reason,
        "repairIssueCount": int(assessment.get("issueCount") or 0),
        "repairableIssueCount": int(assessment.get("repairableIssueCount") or 0),
        "unrepairableIssueCount": int(assessment.get("unrepairableIssueCount") or 0),
        "issues": assessment.get("issues") if isinstance(assessment.get("issues"), list) else [],
    }


def repair_trace(metadata: dict[str, Any]) -> dict[str, Any]:
    issue_count = int(metadata.get("repairIssueCount") or 0)
    status = "ok" if issue_count == 0 else "warning"
    summary = (
        "Report grounding repair checks passed before independent review."
        if issue_count == 0
        else "Report grounding repair downgraded the briefing before independent review."
    )
    return trace_step(
        "report_grounding_repair",
        status,
        summary,
        {
            "schemaVersion": metadata["schemaVersion"],
            "status": metadata["status"],
            "repairAttemptCount": metadata["repairAttemptCount"],
            "repairStopReason": metadata["repairStopReason"],
            "repairIssueCount": metadata["repairIssueCount"],
            "repairableIssueCount": metadata["repairableIssueCount"],
            "unrepairableIssueCount": metadata["unrepairableIssueCount"],
            "issueIds": [str(issue.get("id")) for issue in metadata["issues"]],
        },
        evidence_ids=["safety-policy"],
    )


def _priority_check_issues(briefing: dict[str, Any], hazards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    titles = [_norm(str(hazard.get("title") or "")) for hazard in hazards if hazard.get("title")]
    if not titles:
        return []
    issues = []
    for index, check in enumerate(_strings(briefing.get("priority_checks"))):
        normalized = _norm(check)
        if not any(title and (title in normalized or normalized in title) for title in titles):
            issues.append(_issue(f"priority-check-unmapped-{index + 1}", "briefing.priority_checks", True))
    return issues


def _issue(issue_id: str, affects: str, repairable: bool, *, severity: str = "medium") -> dict[str, Any]:
    return {"id": issue_id, "severity": severity, "affects": [affects], "repairable": repairable}


def _strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _norm(value: str) -> str:
    return " ".join("".join(char.lower() if char.isalnum() else " " for char in value).split())
