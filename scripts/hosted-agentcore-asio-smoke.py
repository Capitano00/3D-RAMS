#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import uuid
from typing import Any, Callable
from urllib import error, request


REPORT_ACCESS_SCHEMA_VERSION = "3d-rams.report-access.v1"


class SmokeFailure(AssertionError):
    pass


def run_smoke(
    invoke_entry: Callable[[dict[str, Any]], dict[str, Any]],
    *,
    case_id: str | None = None,
    require_persistence: bool = True,
) -> dict[str, Any]:
    case_id = case_id or f"case_hosted_smoke_{uuid.uuid4().hex[:10]}"
    conversation_id = f"hosted-smoke-{uuid.uuid4().hex[:10]}"
    checks: list[dict[str, Any]] = []

    clarification = invoke_entry(
        {
            "entryTurn": True,
            "caller": "hosted-smoke",
            "conversationId": f"{conversation_id}-clarify",
            "message": "Can you help me?",
            "runtimeOptions": {"fixturePack": "public-lambeth-thames", "useBedrock": False},
        }
    )
    entry_agent = _entry_agent(clarification)
    pending_status = entry_agent.get("status")
    _assert(pending_status in {"clarification_required", "confirmation_required"}, "entry did not clarify or confirm")
    _assert(_output(clarification).get("run") is None, "clarification turn unexpectedly launched supervisor")
    checks.append({"name": "entry_clarification_or_confirmation", "status": "ok", "entryStatus": pending_status})

    launch = invoke_entry(_confirmed_launch_payload(case_id, conversation_id))
    output = _output(launch)
    run = _dict(output.get("run"))
    report = _dict(output.get("structuredReport"))
    _assert(output.get("caseId") == case_id, "confirmed launch did not preserve caseId")
    _assert(run.get("caseId") == case_id, "supervisor run did not echo caseId")
    _assert(report.get("caseId") == case_id, "structuredReport did not echo caseId")
    _assert(_list(run.get("trace")), "supervisor returned no trace")
    _assert(_list(run.get("evidence")), "supervisor returned no evidence")
    _assert(isinstance(run.get("safety"), dict), "supervisor returned no safety object")
    checks.append(
        {
            "name": "confirmed_entry_launches_supervisor",
            "status": "ok",
            "reportStatus": output.get("reportStatus"),
            "traceSteps": len(_list(run.get("trace"))),
            "evidenceItems": len(_list(run.get("evidence"))),
        }
    )

    material = _dict(run.get("materialIngestion"))
    skipped_reasons = {str(item.get("reason")) for item in _list(material.get("skipped"))}
    _assert(int(material.get("accepted") or 0) >= 1, "authorized material reference was not accepted")
    _assert(int(material.get("skippedCount") or 0) >= 1, "denied material reference was not skipped")
    _assert("denied" in skipped_reasons, "denied material reference did not produce a skip reason")
    checks.append(
        {
            "name": "authorized_and_denied_material_references",
            "status": "ok",
            "accepted": material.get("accepted"),
            "skipped": material.get("skippedCount"),
        }
    )

    persistence = _dict(output.get("persistence"))
    if require_persistence:
        _assert(persistence.get("status") == "stored", "report store write was not verified as stored")
    checks.append({"name": "report_store_write", "status": "ok", "persistenceStatus": persistence.get("status")})
    if not require_persistence and persistence.get("status") != "stored":
        checks.append(
            {
                "name": "identity_bound_lookup",
                "status": "skipped",
                "reason": "report persistence was not stored",
            }
        )
        return redact_public_safe(_summary(case_id=case_id, checks=checks, output=output, run=run, report=report))

    denied_lookup = invoke_entry(
        {
            "frontendInvoke": True,
            "operation": "getReport",
            "caseId": case_id,
            "conversationId": f"{conversation_id}-lookup-denied",
        }
    )
    denied_output = _output(denied_lookup)
    _assert(denied_output.get("reportStatus") == "access_denied", "lookup without ASI context was not denied")
    _assert(denied_output.get("run") is None and denied_output.get("structuredReport") is None, "denied lookup returned report details")
    checks.append({"name": "identity_bound_lookup_denied", "status": "ok"})

    authorized_lookup = invoke_entry(
        {
            "frontendInvoke": True,
            "operation": "getReport",
            "caseId": case_id,
            "conversationId": f"{conversation_id}-lookup-authorized",
            "reportAccess": _report_access(case_id, conversation_id),
        }
    )
    authorized_output = _output(authorized_lookup)
    _assert(authorized_output.get("caseId") == case_id, "authorized lookup returned the wrong caseId")
    _assert(_dict(authorized_output.get("structuredReport")).get("caseId") == case_id, "authorized lookup returned no structuredReport")
    _assert(_dict(authorized_output.get("run")).get("caseId") == case_id, "authorized lookup returned no run")
    checks.append(
        {
            "name": "identity_bound_lookup_authorized",
            "status": "ok",
            "persistenceStatus": _dict(authorized_output.get("persistence")).get("status"),
        }
    )

    return redact_public_safe(
        _summary(case_id=case_id, checks=checks, output=output, run=run, report=report)
    )


def invoke_entry_url(entry_url: str, payload: dict[str, Any], *, timeout: int) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        entry_url,
        data=body,
        headers={"accept": "application/json", "content-type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise SmokeFailure(f"entry proxy returned HTTP {exc.code}: {redact_text(raw[:800])}") from exc
    except error.URLError as exc:
        raise SmokeFailure(f"entry proxy request failed: {redact_text(str(exc))}") from exc

    parsed = json.loads(raw)
    if isinstance(parsed, dict) and isinstance(parsed.get("body"), str):
        body_payload = json.loads(parsed["body"] or "{}")
        if isinstance(body_payload, dict):
            return body_payload
    if not isinstance(parsed, dict):
        raise SmokeFailure("entry proxy returned non-object JSON")
    return parsed


def redact_public_safe(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            if _secret_key(key):
                redacted[key] = "[REDACTED]"
            else:
                redacted[key] = redact_public_safe(item)
        return redacted
    if isinstance(value, list):
        return [redact_public_safe(item) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    return value


def redact_text(text: str) -> str:
    text = re.sub(r"\b(AKIA|ASIA)[A-Z0-9]{16}\b", "[REDACTED_AWS_ACCESS_KEY]", text)
    text = re.sub(r"(?i)(AWS4-HMAC-SHA256\s+Credential=)[^,\s]+", r"\1[REDACTED]", text)
    text = re.sub(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+", r"\1[REDACTED]", text)
    text = re.sub(r"arn:aws:[A-Za-z0-9_:/.-]+", "[REDACTED_AWS_ARN]", text)
    text = re.sub(r"(?<![A-Za-z0-9])\d{12}(?![A-Za-z0-9])", "[REDACTED_ACCOUNT_ID]", text)
    text = re.sub(r"https?://[^\s\"']*(X-Amz-Signature|X-Amz-Credential|signature=|token=)[^\s\"']*", "[REDACTED_SIGNED_URL]", text)
    return text


def _confirmed_launch_payload(case_id: str, conversation_id: str) -> dict[str, Any]:
    return {
        "entryTurn": True,
        "caller": "hosted-smoke",
        "conversationId": conversation_id,
        "entryAgentId": "@3d-rams",
        "caseId": case_id,
        "confirmedByUser": True,
        "reportAccess": _report_access(case_id, conversation_id),
        "intake": {
            "locationText": "8 Albert Embankment, Lambeth",
            "locationCandidate": {
                "label": "8 Albert Embankment and land to the rear",
                "lat": 51.492099,
                "lng": -0.118712,
                "confidence": 0.85,
            },
            "areaScope": {"type": "radius", "meters": 800},
            "userGoal": "hosted smoke pre-visit review",
            "userNotes": "Public-safe hosted smoke fixture. No private client material.",
            "materials": [
                {
                    "materialId": "asio_material_site_access_plan",
                    "sourceSystem": "asio",
                    "type": "application/pdf",
                    "label": "Public fixture access plan",
                    "summary": "Public-safe fixture note for access and site boundary awareness.",
                    "caseId": case_id,
                    "sizeBytes": 124000,
                    "access": {
                        "mode": "asio_authorized_reference",
                        "expiresAt": "2099-01-01T00:00:00Z",
                        "sessionId": conversation_id,
                    },
                },
                {
                    "materialId": "asio_material_services_note_denied",
                    "sourceSystem": "asio",
                    "type": "application/pdf",
                    "label": "Denied public fixture note",
                    "summary": "This reference intentionally exercises denied material handling.",
                    "caseId": case_id,
                    "sizeBytes": 98000,
                    "access": {"mode": "denied", "status": "denied", "sessionId": conversation_id},
                },
            ],
        },
        "runtimeOptions": {
            "fixturePack": "public-lambeth-thames",
            "useBedrock": False,
            "includePlanningFixture": True,
            "simulateMapFailure": False,
        },
    }


def _report_access(case_id: str, session_id: str) -> dict[str, Any]:
    return {
        "schemaVersion": REPORT_ACCESS_SCHEMA_VERSION,
        "mode": "asi_session",
        "caseId": case_id,
        "authorizedCaseIds": [case_id],
        "sessionId": session_id,
        "source": "HOSTED_SMOKE",
    }


def _summary(
    *,
    case_id: str,
    checks: list[dict[str, Any]],
    output: dict[str, Any],
    run: dict[str, Any],
    report: dict[str, Any],
) -> dict[str, Any]:
    return {
        "status": "ok",
        "smoke": "agentcore_asio_hosted",
        "caseId": case_id,
        "checks": checks,
        "supervisor": {
            "workflowMode": output.get("workflowMode"),
            "reportStatus": output.get("reportStatus"),
            "safetyLevel": _dict(run.get("safety")).get("level"),
            "structuredReport": bool(report),
        },
        "publicSafe": True,
    }


def _secret_key(key: str) -> bool:
    lowered = key.lower()
    return any(
        token in lowered
        for token in (
            "authorization",
            "credential",
            "secret",
            "token",
            "signedurl",
            "signed_url",
            "rawcontent",
            "raw_content",
            "privatepayload",
            "private_payload",
        )
    )


def _output(response: dict[str, Any]) -> dict[str, Any]:
    output = response.get("output")
    if not isinstance(output, dict):
        raise SmokeFailure("response missing output object")
    return output


def _entry_agent(response: dict[str, Any]) -> dict[str, Any]:
    entry = _output(response).get("entryAgent")
    if not isinstance(entry, dict):
        raise SmokeFailure("response missing output.entryAgent")
    return entry


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[dict[str, Any]]:
    return value if isinstance(value, list) else []


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeFailure(message)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run hosted AgentCore + ASI/ASI:ONE smoke parity against the signed entry proxy."
    )
    parser.add_argument("--entry-url", default=os.getenv("RAMS_HOSTED_ENTRY_URL") or os.getenv("VITE_CLOUD_ENTRY_PROXY_URL"))
    parser.add_argument("--timeout", type=int, default=int(os.getenv("RAMS_HOSTED_SMOKE_TIMEOUT", "120")))
    parser.add_argument("--case-id", default=os.getenv("RAMS_HOSTED_SMOKE_CASE_ID"))
    parser.add_argument(
        "--allow-unstored",
        action="store_true",
        help="Allow persistence status other than stored. Default requires RAMS_REPORT_STORE_TABLE-backed storage.",
    )
    args = parser.parse_args()

    if not args.entry_url:
        print("Set RAMS_HOSTED_ENTRY_URL or VITE_CLOUD_ENTRY_PROXY_URL to the signed entry proxy /invoke URL.", file=sys.stderr)
        return 2

    try:
        result = run_smoke(
            lambda payload: invoke_entry_url(args.entry_url, payload, timeout=args.timeout),
            case_id=args.case_id,
            require_persistence=not args.allow_unstored,
        )
    except (SmokeFailure, json.JSONDecodeError) as exc:
        print(f"Hosted smoke failed: {redact_text(str(exc))}", file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
