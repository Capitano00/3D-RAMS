from __future__ import annotations

from typing import Any


def architecture_snapshot(
    trace: list[dict[str, Any]],
    request_summary: dict[str, Any],
    sources: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
    safety: dict[str, Any],
    runtime: dict[str, Any],
) -> dict[str, Any]:
    return {
        "runOverview": {
            "caseId": request_summary.get("caseId"),
            "siteName": request_summary["siteName"],
            "goal": request_summary["goal"],
            "coordinate": f"{request_summary['latitude']}, {request_summary['longitude']}",
            "fixturePack": request_summary.get("fixturePack") or "synthetic-default",
            "planningFixture": "enabled" if request_summary["includePlanningFixture"] else "disabled",
            "mapMode": "fallback" if request_summary["simulateMapFailure"] else "fixture",
            "briefingMode": runtime["briefingMode"],
            "safetyLevel": safety["level"],
            "materialReferences": len(request_summary.get("materials") or []),
        },
        "nodes": [
            {"id": "ui", "label": "React/Vite UI", "boundary": "frontend"},
            {"id": "api", "label": "AgentCore invocation endpoint", "boundary": "agentcore runtime"},
            {"id": "agent", "label": "3D-RAMS agent loop", "boundary": "agentcore runtime"},
            {"id": "fixtures", "label": "Fixture data", "boundary": "mock data"},
            {"id": "aws", "label": "Future AWS path", "boundary": "production stretch"},
        ],
        "edges": [
            {"from": "ui", "to": "api", "label": "POST /invocations"},
            {"from": "api", "to": "agent", "label": "validated request"},
            {"from": "agent", "to": "fixtures", "label": "tool calls"},
            {"from": "agent", "to": "ui", "label": "scene, evidence, trace"},
            {"from": "agent", "to": "aws", "label": "Bedrock, DynamoDB, S3, CloudWatch later"},
        ],
        "currentTrace": [
            {
                "id": step["id"],
                "caseId": step.get("caseId") or request_summary.get("caseId"),
                "name": step["name"],
                "status": step["status"],
                "summary": step["summary"],
                "durationMs": step["durationMs"],
                "sourceIds": step["sourceIds"],
                "evidenceIds": step["evidenceIds"],
                "fallbackReason": step["fallbackReason"],
                "output": step["output"],
            }
            for step in trace
        ],
        "sources": sources,
        "evidenceFlow": [
            {
                "id": item["id"],
                "title": item["title"],
                "status": item["status"],
                "feeds": ["annotations", "briefing", "trace"],
            }
            for item in evidence
        ],
        "safetyGate": {
            "allowed": safety["allowed"],
            "level": safety["level"],
            "message": safety["message"],
            "triggeredRules": safety["triggeredRules"],
            "requiresHumanReview": safety["requiresHumanReview"],
            "awsMapping": "Future Bedrock Guardrails plus human approval queue",
        },
        "awsPath": [
            {"local": "Deterministic Python agent loop", "future": "Bedrock model/tool planning"},
            {"local": "One Bedrock briefing step", "future": "Evaluated model-assisted extraction and generation"},
            {"local": "JSON trace in API response", "future": "CloudWatch logs, metrics, traces"},
            {"local": "Evidence list in response", "future": "S3 evidence pack"},
            {"local": "Per-request in-memory run", "future": "DynamoDB run/session record"},
            {"local": "Rule-based safety gate", "future": "Guardrails plus human review"},
        ],
        "realVsMocked": [
            {"component": "Agent workflow", "status": "real deterministic code"},
            {
                "component": "Fixture pack",
                "status": (
                    f"cached public fixture: {runtime.get('fixturePack')}"
                    if runtime.get("fixturePack")
                    else "synthetic default fixtures"
                ),
            },
            {"component": "Bedrock briefing", "status": str(runtime["briefingMode"])},
            {
                "component": "Material ingestion",
                "status": (
                    f"{runtime.get('materialIngestionStatus')} "
                    f"({runtime.get('materialEvidenceCount', 0)} accepted, {runtime.get('materialSkippedCount', 0)} skipped)"
                    if runtime.get("materialIngestionStatus")
                    else "not configured"
                ),
            },
            {"component": "3D viewer", "status": "real local Cesium scene"},
            {
                "component": "Planning documents",
                "status": "cached public-safe notes" if runtime.get("fixturePack") else "synthetic fixture",
            },
            {"component": "Live Google 3D / Earth", "status": "not used in Demo1"},
            {"component": "CloudWatch / S3 / DynamoDB", "status": "production path, not live in MVP"},
        ],
        "runtime": runtime,
    }
