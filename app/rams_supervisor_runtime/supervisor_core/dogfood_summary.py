from __future__ import annotations

from typing import Any


DOGFOOD_SUMMARY_SCHEMA_VERSION = "3d-rams.dogfood-summary.v1"

_TAG_TESTS = {
    "location_evidence_needed": "add_location_evidence_regression",
    "confirmation_pending": "add_location_confirmation_regression",
    "fallback_used": "add_fallback_path_regression",
    "safety_blocked": "add_safety_boundary_regression",
    "review_rework_needed": "add_review_rework_regression",
    "output_quality_gap": "add_output_quality_regression",
}
_TAG_PRIORITY = (
    "location_evidence_needed",
    "confirmation_pending",
    "safety_blocked",
    "review_rework_needed",
    "fallback_used",
    "output_quality_gap",
)


def build_dogfood_summary(run: dict[str, Any], report: dict[str, Any] | None = None) -> dict[str, Any]:
    report = report if isinstance(report, dict) else {}
    tags = []
    confirmation = _dict(run.get("locationConfirmation"))
    status = str(confirmation.get("status") or "")
    if status == "evidence_required":
        tags.append("location_evidence_needed")
    if status in {"confirmation_required", "evidence_required"}:
        tags.append("confirmation_pending")
    if _fallback_used(run, report):
        tags.append("fallback_used")
    if _safety_blocked(run, report):
        tags.append("safety_blocked")
    if _review_rework_needed(run, report):
        tags.append("review_rework_needed")
    if _output_quality_gap(run, report):
        tags.append("output_quality_gap")
    tags = [tag for tag in _TAG_PRIORITY if tag in tags]

    return {
        "schemaVersion": DOGFOOD_SUMMARY_SCHEMA_VERSION,
        "tags": tags,
        "recommendedNextRegressionTest": _TAG_TESTS.get(tags[0]) if tags else "keep_current_regression_pack",
    }


def _fallback_used(run: dict[str, Any], report: dict[str, Any]) -> bool:
    runtime = _dict(run.get("runtime")) or _dict(report.get("runtime"))
    observability = _dict(runtime.get("runtimeObservability"))
    if runtime.get("fallbackReason") or observability.get("fallbackReason"):
        return True
    if str(observability.get("modelPath") or "") == "fallback":
        return True
    contract = _dict(runtime.get("harnessContract"))
    if int(contract.get("fallbackCount") or 0) > 0:
        return True
    return any(str(step.get("status") or "") == "fallback" for step in _list(run.get("trace")) or _list(report.get("trace")))


def _safety_blocked(run: dict[str, Any], report: dict[str, Any]) -> bool:
    safety = _dict(run.get("safety"))
    review_gate = _dict(run.get("reviewGate")) or _dict(report.get("reviewGate"))
    safety_level = str(safety.get("level") or review_gate.get("safetyLevel") or "")
    return str(review_gate.get("status") or "") == "blocked" or "blocked" in safety_level


def _review_rework_needed(run: dict[str, Any], report: dict[str, Any]) -> bool:
    review_gate = _dict(run.get("reviewGate")) or _dict(report.get("reviewGate"))
    return str(review_gate.get("status") or "") in {"review_required", "pending_independent_review"} or bool(
        review_gate.get("requiredRevisions")
    )


def _output_quality_gap(run: dict[str, Any], report: dict[str, Any]) -> bool:
    data_quality = _dict(report.get("dataQuality"))
    grounding = _dict(run.get("reportGroundingRepair"))
    runtime = _dict(run.get("runtime")) or _dict(report.get("runtime"))
    contract = _dict(runtime.get("harnessContract"))
    briefing = _dict(run.get("briefing"))
    reasoning = _dict(run.get("reasoning"))
    return bool(
        data_quality.get("gaps")
        or data_quality.get("warnings")
        or briefing.get("limitations")
        or reasoning.get("gaps")
        or grounding.get("status") not in {None, "", "ok"}
        or int(runtime.get("repairIssueCount") or 0) > 0
        or contract.get("contractCompliant") is False
    )


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[dict[str, Any]]:
    return value if isinstance(value, list) else []
