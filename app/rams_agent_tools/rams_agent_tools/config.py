from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_PLANNING_DATA_ENDPOINT = "https://www.planning.data.gov.uk/entity.json"
DEFAULT_PLANNING_DATA_DATASETS = (
    "conservation-area",
    "listed-building",
    "scheduled-monument",
    "flood-risk-zone",
    "green-belt",
    "article-4-direction-area",
    "tree-preservation-zone",
)


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


@dataclass(frozen=True)
class RuntimeConfig:
    bedrock_requested: bool
    bedrock_enabled: bool
    aws_profile: str | None
    aws_region: str
    bedrock_model_id: str
    bedrock_max_tokens: int
    bedrock_max_model_calls: int
    bedrock_temperature: float
    bedrock_mock_response: bool
    bedrock_simulate_failure: bool
    material_extraction_model_id: str
    material_extraction_max_tokens: int
    llm_provider: str = "bedrock"
    openai_base_url: str | None = None
    openai_api_key: str | None = None
    openai_model_id: str = "gpt-5.4-mini"
    live_planning_data_enabled: bool = False
    planning_data_endpoint: str = DEFAULT_PLANNING_DATA_ENDPOINT
    planning_data_timeout_seconds: float = 2.0
    planning_data_result_limit: int = 25
    planning_data_datasets: tuple[str, ...] = DEFAULT_PLANNING_DATA_DATASETS

    @classmethod
    def from_env(cls, *, request_bedrock: bool = True) -> "RuntimeConfig":
        enabled = _env_bool("ENABLE_BEDROCK", False) and request_bedrock
        provider = os.getenv("RAMS_LLM_PROVIDER", "bedrock").strip().lower()
        openai_model_id = os.getenv("OPENAI_MODEL") or os.getenv("RAMS_OPENAI_MODEL") or "gpt-5.4-mini"
        return cls(
            bedrock_requested=request_bedrock,
            bedrock_enabled=enabled,
            llm_provider=provider,
            aws_profile=os.getenv("AWS_PROFILE") or None,
            aws_region=os.getenv("AWS_REGION", "eu-west-2"),
            bedrock_model_id=os.getenv(
                "BEDROCK_MODEL_ID",
                "anthropic.claude-3-7-sonnet-20250219-v1:0",
            ),
            bedrock_max_tokens=_env_int("BEDROCK_MAX_TOKENS", 1200),
            bedrock_max_model_calls=_env_int("BEDROCK_MAX_MODEL_CALLS", 2),
            bedrock_temperature=_env_float("BEDROCK_TEMPERATURE", 0.2),
            bedrock_mock_response=_env_bool("BEDROCK_MOCK_RESPONSE", False),
            bedrock_simulate_failure=_env_bool("BEDROCK_SIMULATE_FAILURE", False),
            material_extraction_model_id=(
                os.getenv("MATERIAL_EXTRACTION_MODEL_ID")
                or os.getenv("BEDROCK_MATERIAL_EXTRACTION_MODEL_ID")
                or "amazon.nova-lite-v1:0"
            ),
            material_extraction_max_tokens=_env_int("MATERIAL_EXTRACTION_MAX_TOKENS", 900),
            openai_base_url=(os.getenv("OPENAI_BASE_URL") or "").strip().rstrip("/") or None,
            openai_api_key=(os.getenv("OPENAI_API_KEY") or "").strip() or None,
            openai_model_id=openai_model_id,
            live_planning_data_enabled=_env_bool("ENABLE_LIVE_PLANNING_DATA", False),
            planning_data_endpoint=os.getenv(
                "PLANNING_DATA_ENDPOINT",
                DEFAULT_PLANNING_DATA_ENDPOINT,
            ),
            planning_data_timeout_seconds=_env_float("PLANNING_DATA_TIMEOUT_SECONDS", 2.0),
            planning_data_result_limit=max(1, min(_env_int("PLANNING_DATA_RESULT_LIMIT", 25), 100)),
            planning_data_datasets=tuple(
                item.strip()
                for item in os.getenv(
                    "PLANNING_DATA_DATASETS",
                    ",".join(DEFAULT_PLANNING_DATA_DATASETS),
                ).split(",")
                if item.strip()
            ),
        )

    def public_runtime(self, *, status: str, fallback_reason: str | None = None) -> dict[str, object]:
        return {
            "briefingMode": status,
            "bedrockRequested": self.bedrock_requested,
            "bedrockEnabled": self.bedrock_enabled,
            "bedrockUsed": status in {"real", "mocked"} and self.llm_provider != "openai",
            "modelProvider": "openai-compatible" if self.llm_provider == "openai" and self.bedrock_enabled else "bedrock",
            "awsRegion": self.aws_region,
            "modelId": (self.openai_model_id if self.llm_provider == "openai" else self.bedrock_model_id) if self.bedrock_enabled else None,
            "maxTokens": self.bedrock_max_tokens if self.bedrock_enabled else None,
            "maxModelCalls": self.bedrock_max_model_calls if self.bedrock_enabled else None,
            "temperature": self.bedrock_temperature if self.bedrock_enabled else None,
            "materialExtractionModelId": self.material_extraction_model_id,
            "materialExtractionMaxTokens": self.material_extraction_max_tokens if self.bedrock_enabled else None,
            "livePlanningDataEnabled": self.live_planning_data_enabled,
            "fallbackReason": fallback_reason,
        }
