from __future__ import annotations

from typing import Any

from .telemetry import trace_step


def _flatten_text(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        parts: list[str] = []
        for item in value.values():
            parts.extend(_flatten_text(item))
        return parts
    if isinstance(value, list):
        parts = []
        for item in value:
            parts.extend(_flatten_text(item))
        return parts
    return []


def _find_unsupported_generated_claims(text: str, blocked_terms: list[str]) -> list[str]:
    normalized = " ".join(text.lower().split())
    matches: list[str] = []
    for term in blocked_terms:
        start = normalized.find(term)
        while start != -1:
            if not _is_negated_safety_boundary(normalized, start, term):
                matches.append(term)
                break
            start = normalized.find(term, start + len(term))
    return matches


def _is_negated_safety_boundary(text: str, claim_start: int, term: str) -> bool:
    prefix = text[max(0, claim_start - 90) : claim_start]
    claim = text[claim_start : claim_start + len(term)]
    boundary_text = f"{prefix}{claim}"
    safe_boundary_patterns = [
        f"cannot {term}",
        f"can't {term}",
        f"do not {term}",
        f"does not {term}",
        f"must not {term}",
        f"must not be treated as {term}",
        f"not {term}",
        f"not a {term}",
        f"not an {term}",
        f"not operational {term}",
        f"without {term}",
        "not a certified rams or work approval",
        "not certified rams, emergency guidance, or work approval",
    ]
    return any(pattern in boundary_text for pattern in safe_boundary_patterns)


def safety_gate(request: dict[str, Any], briefing: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    user_text = " ".join(
        str(request.get(key, ""))
        for key in ("goal", "useCase", "additionalRequest")
    ).lower()
    blocked_terms = [
        "certified rams",
        "certify rams",
        "emergency route",
        "emergency guidance",
        "guarantee safe",
        "approve work",
        "approved for work",
        "work approval",
        "replace competent",
    ]
    request_rules = [term for term in blocked_terms if term in user_text]
    generated_text = " ".join(_flatten_text(briefing))
    generated_rules = _find_unsupported_generated_claims(generated_text, blocked_terms)
    blocked = bool(request_rules or generated_rules)
    decision = {
        "allowed": not blocked,
        "level": "blocked" if blocked else "review_required",
        "message": (
            "Blocked: this demo cannot certify RAMS, approve work, or provide emergency guidance."
            if blocked
            else "Allowed as a non-certified pre-visit briefing that requires human review."
        ),
        "triggeredRules": sorted(set(request_rules + generated_rules)),
        "triggeredSources": {
            "request": request_rules,
            "generatedBriefing": generated_rules,
        },
        "requiresHumanReview": True,
        "decisionId": "safety-demo1-blocked" if blocked else "safety-demo1-review-required",
    }
    if blocked:
        briefing["headline"] = "Request blocked by safety gate."
        briefing["summary"] = [decision["message"]]
        briefing["priority_checks"] = []

    return decision, trace_step(
        "safety_gate",
        "blocked" if blocked else "ok",
        decision["message"],
        {
            "allowed": decision["allowed"],
            "level": decision["level"],
            "triggeredRules": decision["triggeredRules"],
            "triggeredSources": decision["triggeredSources"],
        },
        evidence_ids=["safety-policy"],
    )
