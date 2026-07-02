import os
from typing import Any


def load_model() -> Any:
    """Get the entry agent model client from the runtime environment."""
    provider = os.getenv("ENTRY_AGENT_PROVIDER", "").strip().lower()
    if provider == "openai" or (not provider and os.getenv("OPENAI_BASE_URL") and os.getenv("OPENAI_API_KEY")):
        from strands.models.openai import OpenAIModel

        return OpenAIModel(
            client_args={
                "api_key": os.environ["OPENAI_API_KEY"],
                "base_url": os.environ["OPENAI_BASE_URL"].rstrip("/"),
            },
            model_id=os.getenv("OPENAI_MODEL") or os.getenv("ENTRY_AGENT_MODEL_ID") or "gpt-5.4-mini",
        )

    from strands.models.bedrock import BedrockModel

    return BedrockModel(model_id=os.getenv("ENTRY_AGENT_MODEL_ID", "amazon.nova-micro-v1:0"))
