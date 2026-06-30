import os
import sys
import unittest
from copy import deepcopy
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
TOOLS_ROOT = APP_ROOT.parent / "rams_agent_tools"
for path in (TOOLS_ROOT, APP_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from supervisor_core.agentcore_adapter import handle_invocation  # noqa: E402
from supervisor_core.agentic_eval import evaluate_agentic_output  # noqa: E402


class EnvPatch:
    def __init__(self, **updates):
        self.updates = updates
        self.previous = {}

    def __enter__(self):
        for key, value in self.updates.items():
            self.previous[key] = os.environ.get(key)
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def __exit__(self, exc_type, exc, tb):
        for key, value in self.previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


class AgenticEvalTests(unittest.TestCase):
    def test_default_eval_uses_mock_model_evaluator_when_configured(self):
        payload = handle_invocation({"input": {"fixturePack": "public-lambeth-thames", "useBedrock": False}})

        with EnvPatch(
            AGENTIC_EVAL_MOCK_RESPONSE="true",
            AGENTIC_EVAL_MODEL_ID="amazon.nova-micro-v1:0",
        ):
            artifact = evaluate_agentic_output(payload)

        self.assertEqual(artifact["schemaVersion"], "3d-rams.agentic-eval.v1")
        self.assertEqual(artifact["mode"], "llm")
        self.assertEqual(artifact["modelCall"]["mode"], "bedrock-mock")
        self.assertEqual(artifact["modelCall"]["modelId"], "amazon.nova-micro-v1:0")
        self.assertEqual(artifact["overall"]["status"], "pass")
        self.assertGreaterEqual(artifact["overall"]["score"], 0.95)
        rubric_statuses = {item["id"]: item["status"] for item in artifact["rubric"]}
        self.assertEqual(rubric_statuses["evidence-support"], "pass")
        self.assertEqual(rubric_statuses["unsupported-claims"], "pass")
        self.assertEqual(rubric_statuses["visualization-readiness"], "pass")
        self.assertEqual(artifact["recommendedFixes"], [])

    def test_eval_fails_affirmative_approval_to_work_claims(self):
        payload = handle_invocation({"input": {"fixturePack": "public-lambeth-thames", "useBedrock": False}})
        mutated = deepcopy(payload)
        mutated["output"]["run"]["briefing"]["headline"] = "This site is approved to start work."

        with EnvPatch(AGENTIC_EVAL_MOCK_RESPONSE="true"):
            artifact = evaluate_agentic_output(mutated)

        self.assertEqual(artifact["overall"]["status"], "fail")
        unsupported = next(item for item in artifact["rubric"] if item["id"] == "unsupported-claims")
        self.assertEqual(unsupported["status"], "fail")
        self.assertTrue(any("approved to start work" in item["message"] for item in unsupported["findings"]))

    def test_eval_warns_when_findings_lack_evidence_references(self):
        payload = handle_invocation({"input": {"fixturePack": "public-lambeth-thames", "useBedrock": False}})
        mutated = deepcopy(payload)
        mutated["output"]["structuredReport"]["findings"][0]["references"]["evidenceIds"] = []

        with EnvPatch(AGENTIC_EVAL_MOCK_RESPONSE="true"):
            artifact = evaluate_agentic_output(mutated)

        self.assertEqual(artifact["overall"]["status"], "warn")
        evidence = next(item for item in artifact["rubric"] if item["id"] == "evidence-support")
        self.assertEqual(evidence["status"], "warn")

    def test_eval_falls_back_when_model_call_fails(self):
        payload = handle_invocation({"input": {"fixturePack": "public-lambeth-thames", "useBedrock": False}})

        with EnvPatch(AGENTIC_EVAL_SIMULATE_FAILURE="true"):
            artifact = evaluate_agentic_output(payload)

        self.assertEqual(artifact["mode"], "fallback")
        self.assertEqual(artifact["overall"]["status"], "warn")
        self.assertTrue(
            any(item["id"] == "model-backed-evaluator" for item in artifact["rubric"])
        )

    def test_llm_mode_can_use_mock_model_evaluator_when_enabled(self):
        payload = handle_invocation({"input": {"fixturePack": "public-lambeth-thames", "useBedrock": False}})

        with EnvPatch(
            AGENTIC_EVAL_MOCK_RESPONSE="true",
            AGENTIC_EVAL_MODEL_ID="amazon.nova-micro-v1:0",
        ):
            artifact = evaluate_agentic_output(payload, mode="llm")

        self.assertEqual(artifact["mode"], "llm")
        self.assertEqual(artifact["llmReview"]["status"], "pass")
        self.assertEqual(artifact["modelCall"]["mode"], "bedrock-mock")
        self.assertEqual(artifact["modelCall"]["phase"], "agentic-eval")
        self.assertEqual(artifact["modelCall"]["modelId"], "amazon.nova-micro-v1:0")
        model_item = next(item for item in artifact["rubric"] if item["id"] == "model-backed-evaluator")
        self.assertEqual(model_item["status"], "pass")


if __name__ == "__main__":
    unittest.main()
