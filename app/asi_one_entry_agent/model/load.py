import os
from typing import Any


def load_model() -> Any:
    """Get the entry agent model client from the runtime environment."""
    provider = os.getenv("ENTRY_AGENT_PROVIDER", "").strip().lower()
    if provider == "bedrock":
        raise RuntimeError("ENTRY_AGENT_PROVIDER=bedrock is disabled; use the OpenAI-compatible entry model.")
    if not os.getenv("OPENAI_BASE_URL") or not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_BASE_URL and OPENAI_API_KEY are required for the OpenAI-compatible entry model.")
    from strands.models.openai import OpenAIModel

    return OpenAIModel(
        client_args={
            "api_key": os.environ["OPENAI_API_KEY"],
            "base_url": os.environ["OPENAI_BASE_URL"].rstrip("/"),
        },
        model_id=os.getenv("OPENAI_MODEL") or os.getenv("ENTRY_AGENT_MODEL_ID") or "gpt-5.4-mini",
    )
