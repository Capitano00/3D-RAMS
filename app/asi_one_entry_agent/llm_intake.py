from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
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
    return mode in {"llm_first", "bedrock", "openai", "model"}


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


def openai_intake_model_json(prompt: dict[str, Any]) -> dict[str, Any]:
    mock_response = os.getenv("ENTRY_INTAKE_MOCK_RESPONSE")
    if mock_response:
        return _coerce_json_object(mock_response)

    base_url = os.getenv("OPENAI_BASE_URL", "").strip().rstrip("/")
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not base_url or not api_key:
        raise IntakeLLMError("OPENAI_BASE_URL and OPENAI_API_KEY are required for OpenAI-compatible entry intake.")

    model_id = os.getenv("OPENAI_MODEL") or os.getenv("ENTRY_INTAKE_MODEL_ID") or os.getenv("ENTRY_AGENT_MODEL_ID") or "gpt-5.4-mini"
    timeout = _int_env("ENTRY_INTAKE_TIMEOUT_SECONDS", 20)
    body = json.dumps(
        {
            "model": model_id,
            "messages": [{"role": "user", "content": _prompt_text(prompt)}],
            "max_tokens": _int_env("ENTRY_INTAKE_MAX_TOKENS", 1800),
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        raise IntakeLLMError(f"OpenAI-compatible entry intake failed: {type(exc).__name__}") from exc

    choices = payload.get("choices") if isinstance(payload, dict) else None
    if not isinstance(choices, list) or not choices:
        raise IntakeLLMError("OpenAI-compatible entry intake response did not include choices.")
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if isinstance(content, list):
        text = "".join(str(part.get("text") or "") for part in content if isinstance(part, dict))
    else:
        text = str(content or "")
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
        raise IntakeLLMError("Entry intake model response did not contain a JSON object.")
    return _coerce_json_object(stripped[start : end + 1])


def _coerce_json_object(raw: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise IntakeLLMError("Entry intake model response was not valid JSON.") from exc
    if not isinstance(parsed, dict):
        raise IntakeLLMError("Entry intake model response JSON must be an object.")
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
        return openai_intake_model_json
    return None
