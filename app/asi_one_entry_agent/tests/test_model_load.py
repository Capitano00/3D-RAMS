from __future__ import annotations

import os
import sys
import types
import unittest
from pathlib import Path
from unittest import mock


ENTRY_APP_ROOT = Path(__file__).resolve().parents[1]
if str(ENTRY_APP_ROOT) not in sys.path:
    sys.path.insert(0, str(ENTRY_APP_ROOT))


class ModelLoadTests(unittest.TestCase):
    def test_openai_gateway_env_selects_openai_model(self):
        calls: dict[str, object] = {}

        class FakeOpenAIModel:
            def __init__(self, **kwargs):
                calls.update(kwargs)

        openai_module = types.ModuleType("strands.models.openai")
        openai_module.OpenAIModel = FakeOpenAIModel
        with mock.patch.dict(
            sys.modules,
            {"strands.models.openai": openai_module},
        ), mock.patch.dict(
            os.environ,
            {
                "OPENAI_BASE_URL": "https://gateway.example/v1/",
                "OPENAI_API_KEY": "test-key",
                "OPENAI_MODEL": "gpt-5.4-mini",
            },
            clear=False,
        ):
            from model.load import load_model

            load_model()

        self.assertEqual(calls["model_id"], "gpt-5.4-mini")
        self.assertEqual(calls["client_args"], {"api_key": "test-key", "base_url": "https://gateway.example/v1"})

    def test_bedrock_provider_is_disabled(self):
        with mock.patch.dict(
            os.environ,
            {"OPENAI_BASE_URL": "", "OPENAI_API_KEY": "", "ENTRY_AGENT_PROVIDER": "bedrock"},
            clear=False,
        ):
            from model.load import load_model

            with self.assertRaisesRegex(RuntimeError, "ENTRY_AGENT_PROVIDER=bedrock is disabled"):
                load_model()

    def test_default_provider_requires_openai_gateway_env(self):
        with mock.patch.dict(
            os.environ,
            {"OPENAI_BASE_URL": "", "OPENAI_API_KEY": "", "ENTRY_AGENT_PROVIDER": ""},
            clear=False,
        ):
            from model.load import load_model

            with self.assertRaisesRegex(RuntimeError, "OPENAI_BASE_URL and OPENAI_API_KEY"):
                load_model()


if __name__ == "__main__":
    unittest.main()
