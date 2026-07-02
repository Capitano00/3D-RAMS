from __future__ import annotations

import os
from typing import Any

from rams_agent_tools.tools import trace_step


def run_independent_review_loop(run: dict[str, Any], *, reviewer_mode: str = "deterministic") -> None:
    max_revisions = _max_revisions(run)
    revision_count = 0
    attempts: list[dict[str, Any]] = []
    review_input = _review_input(run, revision_count)
    run["draftReport"] = review_input["structuredReport"]
    run["reviewInput"] = review_input

    while True:
        review = _review(run, reviewer_mode, revision_count)
        attempts.append(review)
        run.setdefault("trace", []).append(_trace("independent_review_gate", review, revision_count))

        if review["decision"] != "revise":
            break
        if revision_count >= max_revisions:
            review["summary"] = "Independent review still requested revision after the bounded revision limit."
            attempts[-1] = review
            break

        revision_count += 1
        _apply_revision(run, revision_count)
        run["trace"].append(
            trace_step(
                "supervisor_review_revision",
                "warning",
                "Supervisor applied a bounded revision from independent review findings.",
                {"revisionCount": revision_count},
                evidence_ids=["safety-policy"],
            )
        )
        review_input = _review_input(run, revision_count)

    gate_status = {
        "pass": "passed",
        "pass_with_caveats": "passed_with_caveats",
        "block": "blocked",
    }.get(review["decision"], "review_required")
    safety = _dict(run.get("safety"))
    run["reviewGate"] = {
        "schemaVersion": "3d-rams.review-output.v1",
        "status": gate_status,
        "decision": review["decision"],
        "reviewer": review["reviewer"],
        "safetyAllowed": bool(safety.get("allowed")),
        "safetyLevel": str(safety.get("level") or "unknown"),
        "requiresHumanReview": True,
        "message": review["summary"],
        "triggeredRules": _strings(safety.get("triggeredRules")),
        "reviewerNotes": _dedupe([review["summary"], *review["caveats"]]),
        "issues": review["issues"],
        "requiredRevisions": review["requiredRevisions"],
        "caveats": review["caveats"],
        "revisionCount": revision_count,
        "maxRevisionAttempts": max_revisions,
        "attemptCount": len(attempts),
    }
    run["reviewLoop"] = {
        "schemaVersion": "3d-rams.review-loop.v1",
        "mode": reviewer_mode,
        "maxRevisionAttempts": max_revisions,
        "revisionCount": revision_count,
        "attempts": attempts,
    }
    run["finalReportStatus"] = (
        "blocked" if gate_status == "blocked" else "review_passed" if gate_status.startswith("passed") else "review_required"
    )
    if gate_status == "blocked":
        run["hazards"] = []
        run["annotations"] = []
        _append_limit(run, "Independent review blocked normal deep-report delivery.")


def _review_input(run: dict[str, Any], revision_count: int) -> dict[str, Any]:
    evidence = _list(run.get("evidence"))
    return {
        "schemaVersion": "3d-rams.review-input.v1",
        "caseId": run.get("caseId"),
        "intake": _dict(run.get("request")),
        "structuredReport": {
            "schemaVersion": "3d-rams.draft-report.v1",
            "status": "draft",
            "caseId": run.get("caseId"),
            "revisionCount": revision_count,
            "findingCount": len(_list(run.get("hazards"))),
            "annotationCount": len(_list(run.get("annotations"))),
            "evidenceCount": len(evidence),
            "dataQualityGapCount": len(_list(_dict(run.get("reasoning")).get("gaps"))),
        },
        "reasoning": _dict(run.get("reasoning")),
        "evidenceRegister": {"sources": _list(run.get("sources")), "evidence": evidence},
        "traceSummary": [
            {"id": step.get("id"), "name": step.get("name"), "status": step.get("status"), "summary": step.get("summary")}
            for step in _list(run.get("trace"))
        ],
        "safetyBoundary": {
            "nonCertifiedRams": True,
            "requiresHumanReview": bool(_dict(run.get("safety")).get("requiresHumanReview", True)),
        },
    }


def _review(run: dict[str, Any], mode: str, revision_count: int) -> dict[str, Any]:
    grounding_repair = _dict(run.get("reportGroundingRepair"))
    if grounding_repair.get("status") == "review_required":
        issues = [
            _issue(
                str(issue.get("id") or "report-grounding-repair"),
                str(issue.get("severity") or "medium"),
                "Report grounding repair requires human review before delivery.",
                _strings(issue.get("affects")) or ["briefing"],
                "human_review_required",
            )
            for issue in _list(grounding_repair.get("issues"))
        ] or [
            _issue(
                "report-grounding-repair",
                "medium",
                "Report grounding repair requires human review before delivery.",
                ["briefing"],
                "human_review_required",
            )
        ]
        return _output("revise", mode, revision_count, issues=issues, required=issues)

    forced = str(_dict(run.get("request")).get("_reviewDecision") or "").strip().lower()
    if forced in {"pass", "pass_with_caveats", "block"}:
        return _output(forced, mode, revision_count)
    if forced == "revise":
        return _output("revise" if revision_count == 0 else "pass_with_caveats", mode, revision_count)
    if forced in {"revise_forever", "max_revision", "max_revisions"}:
        return _output("revise", mode, revision_count)

    safety = _dict(run.get("safety"))
    if safety.get("allowed") is False:
        return _output(
            "block",
            mode,
            revision_count,
            issues=[_issue("safety-boundary-block", "blocking", str(safety.get("message")), ["safety"], "block_delivery")],
        )

    unsupported = [
        _issue(
            f"unsupported-{hazard.get('id') or index}",
            "medium",
            "Finding lacks source or evidence references.",
            [f"findings.{hazard.get('id') or index}"],
            "add_reference",
        )
        for index, hazard in enumerate(_list(run.get("hazards")))
        if not hazard.get("sourceIds") and not hazard.get("evidenceIds")
    ]
    if unsupported:
        return _output("revise", mode, revision_count, issues=unsupported, required=unsupported)

    caveats = _caveats(run)
    return _output("pass_with_caveats" if caveats else "pass", mode, revision_count, caveats=caveats)


def _output(
    decision: str,
    mode: str,
    revision_count: int,
    *,
    issues: list[dict[str, Any]] | None = None,
    required: list[dict[str, Any]] | None = None,
    caveats: list[str] | None = None,
) -> dict[str, Any]:
    summaries = {
        "pass": "Independent review passed the draft report.",
        "pass_with_caveats": "Independent review passed the draft report with visible caveats.",
        "revise": "Independent review requested a bounded supervisor revision.",
        "block": "Independent review blocked normal deep-report delivery.",
    }
    issue = _issue("review-revision", "medium", "Review requested revision.", ["structuredReport"], "add_caveat")
    return {
        "schemaVersion": "3d-rams.review-output.v1",
        "reviewer": {"name": "review_guardrail", "mode": mode},
        "decision": decision,
        "status": {"pass": "ok", "pass_with_caveats": "warning", "revise": "warning", "block": "blocked"}[decision],
        "summary": summaries[decision],
        "issues": issues or ([issue] if decision == "revise" else []),
        "requiredRevisions": required or ([issue] if decision == "revise" else []),
        "caveats": caveats or (["Independent review passed with caveats visible to the frontend."] if decision == "pass_with_caveats" else []),
        "trace": [],
        "revisionCount": revision_count,
    }


def _apply_revision(run: dict[str, Any], revision_count: int) -> None:
    _append_limit(run, f"Independent review requested revision pass {revision_count}.")
    _dict(run.get("reasoning")).setdefault("gaps", []).append(
        {
            "id": f"review-revision-{revision_count}",
            "severity": "medium",
            "message": "Independent review requested a bounded supervisor revision pass.",
            "affectsSections": ["candidate-findings", "review-boundary"],
        }
    )


def _trace(name: str, review: dict[str, Any], revision_count: int) -> dict[str, Any]:
    return trace_step(
        name,
        str(review["status"]),
        str(review["summary"]),
        {
            "schemaVersion": review["schemaVersion"],
            "decision": review["decision"],
            "reviewerMode": review["reviewer"]["mode"],
            "issueCount": len(review["issues"]),
            "caveatCount": len(review["caveats"]),
            "revisionCount": revision_count,
        },
        evidence_ids=["safety-policy"],
    )


def _caveats(run: dict[str, Any]) -> list[str]:
    caveats = []
    if _list(_dict(run.get("reasoning")).get("gaps")):
        caveats.append("Data-quality gaps remain visible in the reviewed report.")
    if not _dict(_dict(run.get("externalSignals")).get("openWeb")).get("items"):
        caveats.append("Open-web signals were not available or not configured.")
    if not _list(run.get("hazards")):
        caveats.append("No candidate findings are available for deep-report visualization.")
    return _dedupe(caveats)


def _issue(issue_id: str, severity: str, message: str, affects: list[str], action: str) -> dict[str, Any]:
    return {"id": issue_id, "severity": severity, "message": message, "affects": affects, "requiredAction": action}


def _max_revisions(run: dict[str, Any]) -> int:
    raw = _dict(run.get("request")).get("_reviewMaxRevisionAttempts") or os.getenv("RAMS_REVIEW_MAX_REVISIONS") or 2
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        return 2


def _append_limit(run: dict[str, Any], message: str) -> None:
    limits = _dict(run.get("briefing")).setdefault("limitations", [])
    if message not in limits:
        limits.append(message)


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[dict[str, Any]]:
    return value if isinstance(value, list) else []


def _strings(value: Any) -> list[str]:
    return [str(item) for item in value] if isinstance(value, list) else []


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))
