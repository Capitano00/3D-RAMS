from __future__ import annotations

import json
import os
import sys
import types
import unittest
from pathlib import Path
from unittest import mock


APP_ROOT = Path(__file__).resolve().parents[1]
TOOLS_ROOT = APP_ROOT.parent / "rams_agent_tools"
for path in (TOOLS_ROOT, APP_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from rams_agent_tools.bedrock_adapter import (  # noqa: E402
    generate_bedrock_briefing,
    generate_bedrock_material_extraction,
    generate_bedrock_subagent_plan,
)
from rams_agent_tools.config import RuntimeConfig  # noqa: E402
from supervisor_core.planner import SUPERVISOR_HARNESS_SUBAGENTS  # noqa: E402
from supervisor_core.planner import plan_subagent_workflow  # noqa: E402
from supervisor_core.runtime_observability import runtime_observability  # noqa: E402


class FakeResponse:
    def __init__(self, payload: dict):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def openai_config() -> RuntimeConfig:
    return RuntimeConfig(
        bedrock_requested=True,
        bedrock_enabled=True,
        aws_profile=None,
        aws_region="eu-west-2",
        bedrock_model_id="bedrock-unused",
        bedrock_max_tokens=1200,
        bedrock_max_model_calls=2,
        bedrock_temperature=0.2,
        bedrock_mock_response=False,
        bedrock_simulate_failure=False,
        material_extraction_model_id="nova-unused",
        material_extraction_max_tokens=900,
        llm_provider="openai",
        openai_base_url="https://gateway.example/v1",
        openai_api_key="test-key",
        openai_model_id="gpt-5.4-mini",
    )


def fake_chat_response(content: dict, usage: dict | None = None):
    payload = {"choices": [{"message": {"content": json.dumps(content)}}]}
    if usage is not None:
        payload["usage"] = usage
    return FakeResponse(payload)


class OpenAIGatewayTests(unittest.TestCase):
    def test_briefing_uses_openai_compatible_gateway(self):
        seen: dict[str, object] = {}

        def fake_urlopen(request, timeout):
            seen["url"] = request.full_url
            seen["body"] = json.loads(request.data.decode("utf-8"))
            return fake_chat_response(
                {
                    "headline": "Gateway briefing.",
                    "summary": ["Evidence reviewed."],
                    "priority_checks": ["Access route"],
                    "before_site_visit": ["Confirm permits"],
                    "limitations": ["Human review is required."],
                },
                usage={"prompt_tokens": 5, "completion_tokens": 4, "total_tokens": 9},
            )

        with mock.patch("rams_agent_tools.bedrock_adapter.urllib.request.urlopen", side_effect=fake_urlopen):
            briefing, metadata = generate_bedrock_briefing(
                config=openai_config(),
                location={"label": "Test site"},
                hazards=[],
                deterministic_briefing={
                    "headline": "fallback",
                    "summary": [],
                    "priority_checks": [],
                    "before_site_visit": [],
                    "limitations": [],
                },
                evidence=[],
                planning_available=False,
            )

        self.assertEqual(seen["url"], "https://gateway.example/v1/chat/completions")
        self.assertEqual(seen["body"]["model"], "gpt-5.4-mini")
        self.assertEqual(briefing["generation_mode"], "openai-compatible")
        self.assertEqual(metadata["mode"], "openai-compatible")
        self.assertEqual(metadata["modelProvider"], "openai-compatible")
        self.assertEqual(metadata["tokenUsage"], {"promptTokens": 5, "completionTokens": 4, "totalTokens": 9})

    def test_planner_uses_openai_compatible_gateway(self):
        plan = {
            "rationale": "Use bounded Harness subagents.",
            "initial_parallel_groups": ["geospatial_subagent", "planning_subagent", "material_subagent"],
            "sequential_groups": ["hazard_subagent", "open_web_subagent", "review_guardrail"],
            "report_parallel_groups": ["annotation_subagent", "briefing_subagent"],
            "required_evidence": ["resolved location"],
            "missing_inputs": [],
        }
        with mock.patch(
            "rams_agent_tools.bedrock_adapter.urllib.request.urlopen",
            return_value=fake_chat_response(plan),
        ):
            output, metadata = generate_bedrock_subagent_plan(
                config=openai_config(),
                request_summary={"site": "Test"},
                subagent_schemas=[{"name": name} for name in SUPERVISOR_HARNESS_SUBAGENTS],
            )

        self.assertEqual(output["rationale"], "Use bounded Harness subagents.")
        self.assertEqual(metadata["mode"], "openai-compatible")
        self.assertEqual(metadata["phase"], "planner-plan")
        self.assertNotIn("tokenUsage", metadata)

    def test_planner_observability_passes_safe_openai_usage(self):
        plan = {
            "rationale": "Use bounded Harness subagents.",
            "initial_parallel_groups": ["geospatial_subagent", "planning_subagent", "material_subagent"],
            "sequential_groups": ["hazard_subagent", "open_web_subagent", "review_guardrail"],
            "report_parallel_groups": ["annotation_subagent", "briefing_subagent"],
            "required_evidence": ["resolved location"],
            "missing_inputs": [],
        }
        with mock.patch(
            "rams_agent_tools.bedrock_adapter.urllib.request.urlopen",
            return_value=fake_chat_response(
                plan,
                usage={
                    "prompt_tokens": 11,
                    "completion_tokens": 7,
                    "total_tokens": 18,
                    "prompt_tokens_details": {"cached_tokens": 2},
                    "provider_internal": "do-not-copy",
                    "cached_tokens": True,
                },
            ),
        ):
            result = plan_subagent_workflow(config=openai_config(), request_summary={"site": "Test"})

        expected_usage = {"promptTokens": 11, "completionTokens": 7, "totalTokens": 18}
        self.assertEqual(result["tokenUsage"], expected_usage)
        self.assertEqual(result["modelCalls"][0]["tokenUsage"], expected_usage)
        self.assertNotIn("prompt_tokens_details", result["tokenUsage"])
        runtime = openai_config().public_runtime(status="real")
        runtime["plannerMode"] = result["plannerStatus"]
        runtime["activeAgentMode"] = result["activeAgentMode"]
        runtime["modelCallCount"] = len(result["modelCalls"])
        observability = runtime_observability(runtime, result)
        self.assertEqual(observability["tokenUsage"], expected_usage)

    def test_text_material_extraction_uses_openai_compatible_gateway(self):
        with mock.patch(
            "rams_agent_tools.bedrock_adapter.urllib.request.urlopen",
            return_value=fake_chat_response(
                {
                    "summary": "Access route issue found.",
                    "confidence": "medium",
                    "observations": [
                        {
                            "title": "Access route",
                            "category": "access",
                            "description": "Temporary scaffold crosses the inspection path.",
                            "citation_anchor": "user note",
                            "confidence": "medium",
                        }
                    ],
                    "limitations": ["Bounded extraction."],
                },
                usage={"prompt_tokens": 13, "completion_tokens": 8, "total_tokens": 21},
            ),
        ):
            extraction, metadata = generate_bedrock_material_extraction(
                config=openai_config(),
                material_id="mat-1",
                label="Access note",
                content_type="text/plain",
                text="Temporary scaffold crosses the inspection path.",
            )

        self.assertEqual(extraction["status"], "extracted")
        self.assertEqual(extraction["observations"][0]["category"], "access")
        self.assertEqual(metadata["mode"], "openai-compatible")
        self.assertEqual(metadata["tokenUsage"], {"promptTokens": 13, "completionTokens": 8, "totalTokens": 21})

    def test_supervisor_model_loader_selects_openai_model(self):
        calls: dict[str, object] = {}

        class FakeOpenAIModel:
            def __init__(self, **kwargs):
                calls.update(kwargs)

        openai_module = types.ModuleType("strands.models.openai")
        openai_module.OpenAIModel = FakeOpenAIModel
        with mock.patch.dict(sys.modules, {"strands.models.openai": openai_module}), mock.patch.dict(
            os.environ,
            {
                "RAMS_LLM_PROVIDER": "openai",
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


if __name__ == "__main__":
    unittest.main()
