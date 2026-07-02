import os
from typing import Any


def load_model() -> Any:
    """Get the supervisor model client using runtime environment credentials."""
    provider = os.getenv("RAMS_LLM_PROVIDER", "").strip().lower()
    if provider == "openai" or (not provider and os.getenv("OPENAI_BASE_URL") and os.getenv("OPENAI_API_KEY")):
        from strands.models.openai import OpenAIModel

        return OpenAIModel(
            client_args={
                "api_key": os.environ["OPENAI_API_KEY"],
                "base_url": os.environ["OPENAI_BASE_URL"].rstrip("/"),
            },
            model_id=os.getenv("OPENAI_MODEL") or os.getenv("RAMS_OPENAI_MODEL") or "gpt-5.4-mini",
        )

    from strands.models.bedrock import BedrockModel

    return BedrockModel(
        model_id=os.getenv(
            "BEDROCK_MODEL_ID",
            "anthropic.claude-3-7-sonnet-20250219-v1:0",
        )
    )
