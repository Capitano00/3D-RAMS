from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


AWS_TRACE_MAPPING = {
    "resolve_location": "CloudWatch span: tool.resolve_location",
    "load_geospatial_features": "CloudWatch span: tool.load_geospatial_features",
    "build_scene_config": "CloudWatch span: tool.build_scene_config",
    "load_planning_context": "CloudWatch span: tool.load_planning_context",
    "extract_hazard_notes": "Bedrock/CloudWatch span: tool.extract_hazard_notes",
    "ingest_material_references": "CloudWatch span: tool.ingest_material_references",
    "search_open_web_signals": "CloudWatch span: tool.search_open_web_signals",
    "create_annotations": "CloudWatch span: tool.create_annotations",
    "generate_site_brief": "Bedrock/CloudWatch span: tool.generate_site_brief",
    "plan_subagent_workflow": "Bedrock/CloudWatch span: supervisor.plan_subagent_workflow",
    "reason_over_evidence": "Bedrock/CloudWatch span: supervisor.reason_over_evidence",
    "generate_bedrock_briefing": "Bedrock/CloudWatch span: tool.generate_bedrock_briefing",
    "safety_gate": "Guardrails/CloudWatch span: tool.safety_gate",
}


def trace_step(
    name: str,
    status: str,
    summary: str,
    output: dict[str, Any],
    *,
    source_ids: list[str] | None = None,
    evidence_ids: list[str] | None = None,
    fallback_reason: str | None = None,
    duration_ms: int = 0,
    policy_decision: dict[str, Any] | None = None,
) -> dict[str, Any]:
    timestamp = datetime.now(timezone.utc).isoformat()
    step = {
        "id": f"trace-{name}",
        "name": name,
        "type": "tool",
        "status": status,
        "summary": summary,
        "timestamp": timestamp,
        "startedAt": timestamp,
        "endedAt": timestamp,
        "durationMs": duration_ms,
        "sourceIds": source_ids or [],
        "evidenceIds": evidence_ids or [],
        "fallbackReason": fallback_reason,
        "awsMapping": {
            "service": "future AWS observability",
            "spanName": AWS_TRACE_MAPPING.get(name, f"CloudWatch span: tool.{name}"),
        },
        "output": output,
    }
    step["policyDecision"] = _policy_decision(name, status, fallback_reason, policy_decision)
    return step


def _policy_decision(
    name: str,
    status: str,
    fallback_reason: str | None,
    policy_decision: dict[str, Any] | None,
) -> dict[str, str]:
    default_decision = _decision_from_status(status, fallback_reason)
    if not policy_decision:
        return {
            "tool_name": name,
            "decision": default_decision,
            "reason_code": _reason_code(status, fallback_reason, default_decision),
            "source": "supervisor_runtime",
        }
    return {
        "tool_name": str(policy_decision.get("tool_name") or name),
        "decision": str(policy_decision.get("decision") or default_decision),
        "reason_code": _safe_code(policy_decision.get("reason_code"))
        or _reason_code(status, fallback_reason, default_decision),
        "source": str(policy_decision.get("source") or "supervisor_runtime"),
    }


def _decision_from_status(status: str, fallback_reason: str | None) -> str:
    if status == "blocked":
        return "reject"
    if status == "disabled":
        return "skip"
    if status == "fallback" or fallback_reason:
        return "downgrade"
    return "allow"


def _reason_code(status: str, fallback_reason: str | None, decision: str) -> str:
    return _safe_code(fallback_reason) or {
        "allow": "runtime_path_allowed",
        "skip": "runtime_path_skipped",
        "reject": "runtime_path_rejected",
        "downgrade": "runtime_path_downgraded",
    }.get(decision, _safe_code(status) or "runtime_policy_decision")


def _safe_code(value: Any) -> str:
    code = str(value or "").strip().lower()
    if not code or len(code) > 80:
        return ""
    if any(ch and not (ch.isalnum() or ch == "_") for ch in code):
        return ""
    return code
