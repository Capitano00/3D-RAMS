from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


APP_ROOT = Path(__file__).resolve().parents[1]
TOOLS_ROOT = APP_ROOT.parent / "rams_agent_tools"
for path in (TOOLS_ROOT, APP_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from rams_agent_tools.config import RuntimeConfig  # noqa: E402
from supervisor_core.planner import plan_subagent_workflow  # noqa: E402


def bedrock_config() -> RuntimeConfig:
    return RuntimeConfig(
        bedrock_requested=True,
        bedrock_enabled=True,
        aws_profile=None,
        aws_region="eu-west-2",
        bedrock_model_id="test-model",
        bedrock_max_tokens=1200,
        bedrock_max_model_calls=1,
        bedrock_temperature=0.2,
        bedrock_mock_response=True,
        bedrock_simulate_failure=False,
        material_extraction_model_id="test-material-model",
        material_extraction_max_tokens=900,
    )


def deterministic_config() -> RuntimeConfig:
    config = bedrock_config()
    return RuntimeConfig(
        bedrock_requested=False,
        bedrock_enabled=False,
        aws_profile=config.aws_profile,
        aws_region=config.aws_region,
        bedrock_model_id=config.bedrock_model_id,
        bedrock_max_tokens=config.bedrock_max_tokens,
        bedrock_max_model_calls=config.bedrock_max_model_calls,
        bedrock_temperature=config.bedrock_temperature,
        bedrock_mock_response=False,
        bedrock_simulate_failure=False,
        material_extraction_model_id=config.material_extraction_model_id,
        material_extraction_max_tokens=config.material_extraction_max_tokens,
    )


def valid_plan() -> dict:
    return {
        "rationale": "Use bounded Harness subagents.",
        "initial_parallel_groups": ["geospatial_subagent", "planning_subagent", "material_subagent"],
        "sequential_groups": ["hazard_subagent", "open_web_subagent", "review_guardrail"],
        "report_parallel_groups": ["annotation_subagent", "briefing_subagent"],
        "required_evidence": ["resolved location"],
        "missing_inputs": [],
    }


def metadata() -> dict:
    return {
        "mode": "bedrock-mock",
        "modelId": "test-model",
        "awsRegion": "eu-west-2",
        "modelCallCount": 1,
        "latencyMs": 3,
    }


class PlannerValidationTests(unittest.TestCase):
    def test_valid_model_plan_is_kept(self):
        result = plan_with_model(valid_plan())

        self.assertEqual(result["plannerStatus"], "mocked")
        self.assertEqual(result["activeAgentMode"], "llm-planner-mock")
        self.assertEqual(result["fallback"], {"status": "not_used", "reason": None})
        self.assertEqual(result["plan"]["initialParallelGroups"], valid_plan()["initial_parallel_groups"])
        self.assertEqual(result["trace"]["status"], "ok")

    def test_unknown_subagent_falls_back_without_leaking_model_plan(self):
        plan = valid_plan()
        plan["initial_parallel_groups"] = ["geospatial_subagent", "planning_subagent", "shell_subagent"]

        result = plan_with_model(plan)

        self.assert_fallback(result, "unknown_subagent")
        self.assertNotIn("shell_subagent", json.dumps(result))

    def test_duplicate_subagent_falls_back(self):
        plan = valid_plan()
        plan["initial_parallel_groups"] = ["geospatial_subagent", "planning_subagent", "geospatial_subagent"]

        result = plan_with_model(plan)

        self.assert_fallback(result, "duplicate_subagent")

    def test_missing_dependency_falls_back(self):
        plan = valid_plan()
        plan["sequential_groups"] = ["open_web_subagent", "review_guardrail"]

        result = plan_with_model(plan)

        self.assert_fallback(result, "missing_dependency")

    def test_wrong_phase_falls_back(self):
        plan = valid_plan()
        plan["sequential_groups"] = ["open_web_subagent", "review_guardrail"]
        plan["report_parallel_groups"] = ["annotation_subagent", "hazard_subagent"]

        result = plan_with_model(plan)

        self.assert_fallback(result, "wrong_phase")

    def test_deterministic_plan_is_default_when_bedrock_is_not_requested(self):
        result = plan_subagent_workflow(config=deterministic_config(), request_summary={"agentMode": "deterministic"})

        self.assertEqual(result["plannerStatus"], "deterministic")
        self.assertEqual(result["activeAgentMode"], "deterministic-planner")
        self.assertEqual(result["plan"]["initialParallelGroups"], valid_plan()["initial_parallel_groups"])
        self.assertEqual(result["trace"]["status"], "ok")

    def assert_fallback(self, result: dict, reason: str) -> None:
        self.assertEqual(result["plannerStatus"], "fallback")
        self.assertEqual(result["activeAgentMode"], "deterministic-planner-fallback")
        self.assertEqual(result["fallback"], {"status": "used", "reason": reason})
        self.assertEqual(result["trace"]["status"], "fallback")
        self.assertEqual(result["trace"]["fallbackReason"], reason)
        self.assertEqual(result["plan"]["initialParallelGroups"], valid_plan()["initial_parallel_groups"])


def plan_with_model(plan: dict) -> dict:
    with patch("supervisor_core.planner.generate_bedrock_subagent_plan", return_value=(plan, metadata())):
        return plan_subagent_workflow(config=bedrock_config(), request_summary={"agentMode": "llm"})


if __name__ == "__main__":
    unittest.main()
