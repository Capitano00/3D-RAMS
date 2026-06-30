from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any


REPORT_ACCESS_SCHEMA_VERSION = "3d-rams.report-access.v1"
REPORT_ACCESS_BINDING_SCHEMA_VERSION = "3d-rams.report-access-binding.v1"

_PRODUCTION_MODES = {"asi_identity", "asi_session"}
_DEV_MODE = "dev_local"


def authorize_report_lookup(
    case_id: str,
    access_context: dict[str, Any] | None,
    *,
    stored_binding: dict[str, Any] | None = None,
    dev_lookup_allowed: bool = False,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Return a JSON-safe authorization decision without echoing raw identity values."""
    checked_at = now or datetime.now(timezone.utc)
    context = _normalize_access_context(case_id, access_context)
    if context is None:
        return _decision("denied", case_id, "missing_report_access_context")

    mode = context["mode"]
    if mode == _DEV_MODE:
        if not dev_lookup_allowed:
            return _decision("denied", case_id, "dev_report_lookup_disabled", mode=mode)
    elif mode not in _PRODUCTION_MODES:
        return _decision("denied", case_id, "unsupported_report_access_mode", mode=mode)

    if case_id not in context["authorizedCaseIds"]:
        return _decision("denied", case_id, "case_not_bound_to_access_context", mode=mode)

    expiry_error = _expiry_error(context.get("expiresAt"), checked_at)
    if expiry_error:
        return _decision("denied", case_id, expiry_error, mode=mode)

    if mode == "asi_identity" and not context.get("subjectId"):
        return _decision("denied", case_id, "missing_asi_subject", mode=mode)
    if mode == "asi_session" and not context.get("sessionId"):
        return _decision("denied", case_id, "missing_asi_session", mode=mode)

    if stored_binding is None:
        return _decision("authorized", case_id, "access_context_valid", mode=mode)

    binding = _normalize_binding(stored_binding)
    if binding is None:
        return _decision("denied", case_id, "report_missing_access_binding", mode=mode)
    if binding["caseId"] != case_id:
        return _decision("denied", case_id, "report_case_binding_mismatch", mode=mode)

    binding_expiry_error = _expiry_error(binding.get("expiresAt"), checked_at)
    if binding_expiry_error:
        return _decision("denied", case_id, "report_access_binding_expired", mode=mode)

    if binding.get("mode") == _DEV_MODE and not dev_lookup_allowed:
        return _decision("denied", case_id, "dev_report_lookup_disabled", mode=mode)

    subject_hash = binding.get("subjectIdHash")
    session_hash = binding.get("sessionIdHash")
    if subject_hash and _hash_identity("subject", context.get("subjectId")) != subject_hash:
        return _decision("denied", case_id, "report_subject_mismatch", mode=mode)
    if session_hash and _hash_identity("session", context.get("sessionId")) != session_hash:
        return _decision("denied", case_id, "report_session_mismatch", mode=mode)
    if binding.get("mode") != _DEV_MODE and not subject_hash and not session_hash:
        return _decision("denied", case_id, "report_missing_identity_binding", mode=mode)

    return _decision("authorized", case_id, "case_binding_authorized", mode=mode)


def build_report_access_binding(output: dict[str, Any]) -> dict[str, Any] | None:
    case_id = _text(output.get("caseId"))
    if not case_id:
        return None

    access_context = extract_report_access_context(output)
    context = _normalize_access_context(case_id, access_context)
    if context is None:
        return None

    subject_hash = _hash_identity("subject", context.get("subjectId"))
    session_hash = _hash_identity("session", context.get("sessionId"))
    if context["mode"] != _DEV_MODE and not subject_hash and not session_hash:
        return None

    binding = {
        "schemaVersion": REPORT_ACCESS_BINDING_SCHEMA_VERSION,
        "caseId": case_id,
        "mode": context["mode"],
        "authorizedCaseIds": [case_id],
    }
    if subject_hash:
        binding["subjectIdHash"] = subject_hash
    if session_hash:
        binding["sessionIdHash"] = session_hash
    if context.get("expiresAt"):
        binding["expiresAt"] = context["expiresAt"]
    if context.get("source"):
        binding["source"] = context["source"]
    return binding


def extract_report_access_context(value: dict[str, Any]) -> dict[str, Any] | None:
    for key in ("reportAccess", "reportAccessContext", "accessContext"):
        candidate = value.get(key)
        if isinstance(candidate, dict):
            return candidate

    run = value.get("run")
    if isinstance(run, dict):
        upstream = run.get("upstream")
        if isinstance(upstream, dict):
            candidate = upstream.get("reportAccess")
            if isinstance(candidate, dict):
                return candidate

    upstream = value.get("upstream") or value.get("agentcoreUpstream")
    if isinstance(upstream, dict):
        candidate = upstream.get("reportAccess")
        if isinstance(candidate, dict):
            return candidate

    return None


def _normalize_access_context(case_id: str, value: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None

    mode = _text(value.get("mode"))
    if not mode:
        mode = "asi_identity" if _text(value.get("subjectId")) else "asi_session"
    mode = mode.lower()

    authorized_case_ids = _string_list(value.get("authorizedCaseIds"))
    explicit_case_id = _text(value.get("caseId"))
    if explicit_case_id:
        authorized_case_ids.append(explicit_case_id)

    deduped_cases = []
    for item in authorized_case_ids:
        if item not in deduped_cases:
            deduped_cases.append(item)

    return {
        "schemaVersion": _text(value.get("schemaVersion")) or REPORT_ACCESS_SCHEMA_VERSION,
        "mode": mode,
        "caseId": explicit_case_id or case_id,
        "authorizedCaseIds": deduped_cases,
        "subjectId": _text(value.get("subjectId")),
        "sessionId": _text(value.get("sessionId")),
        "expiresAt": _text(value.get("expiresAt")),
        "source": _text(value.get("source")),
    }


def _normalize_binding(value: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    case_id = _text(value.get("caseId"))
    if not case_id:
        return None
    return {
        "schemaVersion": _text(value.get("schemaVersion")) or REPORT_ACCESS_BINDING_SCHEMA_VERSION,
        "caseId": case_id,
        "mode": (_text(value.get("mode")) or "").lower(),
        "subjectIdHash": _text(value.get("subjectIdHash")),
        "sessionIdHash": _text(value.get("sessionIdHash")),
        "expiresAt": _text(value.get("expiresAt")),
    }


def _hash_identity(kind: str, value: Any) -> str | None:
    text = _text(value)
    if not text:
        return None
    payload = f"3d-rams-report-access:{kind}:{text}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _expiry_error(value: Any, now: datetime) -> str | None:
    text = _text(value)
    if not text:
        return None
    try:
        expires_at = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return "invalid_report_access_expiry"
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= now:
        return "report_access_expired"
    return None


def _decision(status: str, case_id: str, reason: str, *, mode: str | None = None) -> dict[str, Any]:
    decision = {
        "schemaVersion": REPORT_ACCESS_SCHEMA_VERSION,
        "status": status,
        "reason": reason,
        "caseId": case_id,
    }
    if mode:
        decision["mode"] = mode
    return decision


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
