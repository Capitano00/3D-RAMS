from __future__ import annotations

import json
import os
from typing import Any, Callable


class IntakeLLMError(RuntimeError):
    pass


def should_use_llm_intake(payload: dict[str, Any]) -> bool:
    mode = os.getenv("ENTRY_INTAKE_MODE", "llm_first").strip().lower()
    if mode in {"deterministic", "disabled", "off"}:
        return False
    runtime_options = payload.get("runtimeOptions") if isinstance(payload.get("runtimeOptions"), dict) else {}
    if runtime_options.get("useBedrock") is False:
        return False
    return mode in {"llm_first", "bedrock", "model"}


def deterministic_fallback_enabled() -> bool:
    fallback = os.getenv("ENTRY_INTAKE_FALLBACK", "deterministic").strip().lower()
    return fallback in {"deterministic", "true", "1", "yes", "fallback"}


def bedrock_intake_model_json(prompt: dict[str, Any]) -> dict[str, Any]:
    mock_response = os.getenv("ENTRY_INTAKE_MOCK_RESPONSE")
    if mock_response:
        return _coerce_json_object(mock_response)

    if not _has_aws_credential_context():
        raise IntakeLLMError("No AWS credential context is available for Bedrock entry intake.")

    try:
        import boto3
        from botocore.config import Config
    except ImportError as exc:
        raise IntakeLLMError("boto3 and botocore are required for Bedrock entry intake.") from exc

    timeout = _int_env("ENTRY_INTAKE_TIMEOUT_SECONDS", 20)
    max_tokens = _int_env("ENTRY_INTAKE_MAX_TOKENS", 1800)
    model_id = (
        os.getenv("ENTRY_INTAKE_MODEL_ID")
        or os.getenv("ENTRY_AGENT_MODEL_ID")
        or "amazon.nova-micro-v1:0"
    )
    region = os.getenv("AWS_REGION", "eu-west-2")

    try:
        client = boto3.client(
            "bedrock-runtime",
            region_name=region,
            config=Config(
                connect_timeout=min(timeout, 10),
                read_timeout=timeout,
                retries={"max_attempts": _int_env("ENTRY_INTAKE_MAX_RETRIES", 1)},
            ),
        )
        response = client.converse(
            modelId=model_id,
            messages=[
                {
                    "role": "user",
                    "content": [{"text": _prompt_text(prompt)}],
                }
            ],
            inferenceConfig={"maxTokens": max_tokens, "temperature": 0.0},
        )
    except Exception as exc:  # noqa: BLE001 - caller converts model failures to deterministic fallback.
        raise IntakeLLMError(f"Bedrock entry intake failed: {type(exc).__name__}") from exc

    text = "".join(
        block.get("text", "")
        for block in response.get("output", {}).get("message", {}).get("content", [])
        if isinstance(block, dict)
    )
    return _extract_json_object(text)


def _prompt_text(prompt: dict[str, Any]) -> str:
    policy = {
        "strict_output": "Return only valid JSON. Do not wrap it in Markdown.",
        "allowed_statuses": ["clarification_required", "confirmation_required", "launch_ready"],
        "launch_policy": (
            "Never choose launch_ready unless the user has confirmed the structured intake and the intake has "
            "locationText or locationCandidate lat/lng, areaScope.meters, and userGoal."
        ),
        "conversation_policy": (
            "Ask only for genuinely missing critical information. Keep assistantMessage concise and user-facing. "
            "Do not claim certified RAMS, emergency guidance, legal approval, or approval to work."
        ),
        "required_json_shape": {
            "status": "clarification_required | confirmation_required | launch_ready",
            "assistantMessage": "short text for the user",
            "clarifyingQuestions": ["only missing critical questions"],
            "confirmation": {"summary": "confirmation text", "actions": ["confirm", "revise"]},
            "intake": {
                "locationText": "string or null",
                "locationCandidate": {"label": "string", "lat": 0.0, "lng": 0.0, "confidence": 0.0},
                "areaScope": {"type": "radius", "meters": 0},
                "userGoal": "string",
                "userNotes": "string",
                "materials": [],
            },
        },
    }
    return json.dumps({"policy": policy, "entry_intake_prompt": prompt}, ensure_ascii=True)


def _extract_json_object(text: str) -> dict[str, Any]:
    stripped = str(text or "").strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        stripped = stripped.removeprefix("json").strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end <= start:
        raise IntakeLLMError("Bedrock entry intake response did not contain a JSON object.")
    return _coerce_json_object(stripped[start : end + 1])


def _coerce_json_object(raw: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise IntakeLLMError("Bedrock entry intake response was not valid JSON.") from exc
    if not isinstance(parsed, dict):
        raise IntakeLLMError("Bedrock entry intake response JSON must be an object.")
    return parsed


def _has_aws_credential_context() -> bool:
    return any(
        os.getenv(name)
        for name in (
            "AWS_ACCESS_KEY_ID",
            "AWS_PROFILE",
            "AWS_WEB_IDENTITY_TOKEN_FILE",
            "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI",
            "AWS_CONTAINER_CREDENTIALS_FULL_URI",
            "AWS_EXECUTION_ENV",
            "AWS_LAMBDA_FUNCTION_NAME",
        )
    )


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def select_model_json(
    payload: dict[str, Any],
    explicit_model_json: Callable[[dict[str, Any]], dict[str, Any] | str] | None,
) -> Callable[[dict[str, Any]], dict[str, Any] | str] | None:
    if explicit_model_json is not None:
        return explicit_model_json
    if should_use_llm_intake(payload):
        return bedrock_intake_model_json
    return None
