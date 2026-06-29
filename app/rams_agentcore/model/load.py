import os

from strands.models.bedrock import BedrockModel


def load_model() -> BedrockModel:
    """Get Bedrock model client using IAM credentials."""
    return BedrockModel(
        model_id=os.getenv(
            "BEDROCK_MODEL_ID",
            "anthropic.claude-3-7-sonnet-20250219-v1:0",
        )
    )
