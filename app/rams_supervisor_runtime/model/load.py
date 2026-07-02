import os
from typing import Any


def load_model() -> Any:
    """Get the supervisor model client using runtime environment credentials."""
    provider = os.getenv("RAMS_LLM_PROVIDER", "").strip().lower()
    if provider == "bedrock":
        raise RuntimeError("RAMS_LLM_PROVIDER=bedrock is disabled; use the OpenAI-compatible supervisor model.")
    if not os.getenv("OPENAI_BASE_URL") or not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_BASE_URL and OPENAI_API_KEY are required for the OpenAI-compatible supervisor model.")
    from strands.models.openai import OpenAIModel

    return OpenAIModel(
        client_args={
            "api_key": os.environ["OPENAI_API_KEY"],
            "base_url": os.environ["OPENAI_BASE_URL"].rstrip("/"),
        },
        model_id=os.getenv("OPENAI_MODEL") or os.getenv("RAMS_OPENAI_MODEL") or "gpt-5.4-mini",
    )
