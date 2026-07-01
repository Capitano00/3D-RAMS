import importlib.util
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
SIDECAR_MAIN = REPO_ROOT / "agentcore-prototype" / "app" / "fieldbrief_agent" / "main.py"

sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(BACKEND_ROOT))

from backend.app.run_store import clear_all_runs_for_tests  # noqa: E402


def fake_nearest_postcode_response():
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "status": 200,
        "result": [
            {
                "postcode": "BN2 0QU",
                "outcode": "BN2",
                "latitude": 50.8253,
                "longitude": -0.1251,
                "admin_district": "Brighton and Hove",
                "admin_ward": "Queen's Park",
                "parish": "Brighton and Hove, unparished area",
                "region": "South East",
                "country": "England",
            }
        ],
    }
    return response


def assert_review_pack_contract(testcase, response):
    run = response["run"]
    result = run["result"]
    ui_state = result["uiState"]
    testcase.assertEqual(response["action"], "confirmed_location")
    testcase.assertEqual(response["route"], "confirm_location")
    testcase.assertEqual(run["status"], "completed")
    testcase.assertEqual(run["finalUiState"]["safety"]["level"], "review_required")
    testcase.assertGreaterEqual(len(run["toolResults"]), 5)
    testcase.assertGreaterEqual(len(run["steps"]), 5)
    testcase.assertIsInstance(result["briefing"], dict)
    testcase.assertIsInstance(ui_state["hazards"], list)
    testcase.assertGreater(len(ui_state["hazards"]), 0)
    testcase.assertIsInstance(result["evidence"], list)
    testcase.assertIsInstance(result["trace"], list)
    testcase.assertIsInstance(result["modelCalls"], list)
    testcase.assertEqual(result["runtime"]["modelCallCount"], run["modelCallsUsed"])
    testcase.assertTrue(result["safety"]["requiresHumanReview"])
    testcase.assertIn("not", " ".join(result["briefing"].get("limitations", [])).lower())


def load_sidecar_module():
    spec = importlib.util.spec_from_file_location("fieldbrief_agent_sidecar_test", SIDECAR_MAIN)
    if not spec or not spec.loader:
        raise RuntimeError(f"Unable to load sidecar module from {SIDECAR_MAIN}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AgentCoreSidecarTests(unittest.TestCase):
    def setUp(self):
        os.environ["ENABLE_BEDROCK"] = "false"
        os.environ["DURABLE_RUN_PROCESS_INLINE"] = "true"
        os.environ.pop("APP_ACCESS_TOKEN_HASH", None)
        clear_all_runs_for_tests()
        self.sidecar = load_sidecar_module()

    def test_invocations_accepts_agentcore_prompt_shape_without_starting_help_run(self):
        client = TestClient(self.sidecar.app)

        response = client.post("/invocations", json={"prompt": "How does this work?", "useBedrock": False})

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "success")
        self.assertEqual(body["details"]["action"], "answered_from_memory")
        self.assertEqual(body["details"]["route"], "help")
        self.assertFalse(body["details"]["sidecar"]["agentCoreRuntimeLive"])
        self.assertEqual(body["details"]["sidecar"]["agentCoreMemory"], "disabled")

    def test_unsafe_request_blocks_before_model_or_review_tools(self):
        result = self.sidecar.invoke({"message": "Please certify RAMS and approve work today.", "useBedrock": False})

        self.assertEqual(result["action"], "started_run")
        self.assertEqual(result["run"]["status"], "completed")
        self.assertEqual(result["run"]["currentStep"], "safety_gate")
        self.assertEqual(result["run"]["modelCallsUsed"], 0)
        self.assertEqual(result["run"]["safetyResult"]["level"], "blocked")

    def test_coordinate_request_waits_for_confirmation_before_tools(self):
        with patch("backend.app.location_resolver.httpx.get", return_value=fake_nearest_postcode_response()):
            result = self.sidecar.invoke(
                {
                    "message": "I want to visit 50.825351, -0.125125 tomorrow for a roof survey.",
                    "useBedrock": False,
                }
            )

        self.assertEqual(result["run"]["status"], "waiting_for_location_confirmation")
        self.assertEqual(result["run"]["toolResults"], [])
        self.assertEqual(result["run"]["result"]["locationCandidates"][0]["name"], "Coordinate 50.825351, -0.125125")
        self.assertEqual(result["sidecar"]["trafficPolicy"], "parallel-sidecar-no-teammate-traffic")

    def test_chat_only_confirmation_does_not_run_tools(self):
        first = self.sidecar.invoke(
            {
                "message": "I want to visit Greenacre Solar Farm tomorrow for a survey. Please prepare a pre-visit RAMS-style review pack.",
                "useBedrock": False,
            }
        )
        chat_confirm = self.sidecar.invoke(
            {
                "sessionId": first["run"]["sessionId"],
                "message": "yes",
                "useBedrock": False,
            }
        )

        self.assertEqual(chat_confirm["action"], "answered_from_memory")
        self.assertEqual(chat_confirm["route"], "confirm_by_chat")
        self.assertEqual(first["run"]["status"], "waiting_for_location_confirmation")
        self.assertEqual(first["run"]["toolResults"], [])

    def test_confirm_location_action_runs_review_workflow_with_current_contract_shape(self):
        client = TestClient(self.sidecar.app)
        first = self.sidecar.invoke(
            {
                "message": "I want to visit Greenacre Solar Farm tomorrow for a survey. Please prepare a pre-visit RAMS-style review pack.",
                "useBedrock": False,
            }
        )
        candidate_id = first["run"]["result"]["locationCandidates"][0]["candidateId"]

        response = client.post(
            "/invocations",
            json={
                "action": "confirm_location",
                "runId": first["run"]["runId"],
                "candidateId": candidate_id,
                "useBedrock": False,
            },
        )
        confirmed = response.json()["details"]

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")
        assert_review_pack_contract(self, confirmed)
        self.assertEqual(confirmed["run"]["result"]["uiState"]["location"]["label"], "Greenacre Solar Farm")
        self.assertEqual(confirmed["sidecar"]["confirmLocationAction"], "confirm_location")

    def test_coordinate_happy_path_can_be_confirmed_through_sidecar_action(self):
        with patch("backend.app.location_resolver.httpx.get", return_value=fake_nearest_postcode_response()):
            first = self.sidecar.invoke(
                {
                    "message": "I want to visit 50.825351, -0.125125 tomorrow for a roof survey.",
                    "useBedrock": False,
                }
            )
        candidate_id = first["run"]["result"]["locationCandidates"][0]["candidateId"]

        confirmed = self.sidecar.invoke(
            {
                "action": "confirm_location",
                "runId": first["run"]["runId"],
                "candidateId": candidate_id,
                "useBedrock": False,
            }
        )

        assert_review_pack_contract(self, confirmed)
        self.assertEqual(confirmed["run"]["confirmedLocation"]["source"], "user-supplied-coordinate")
        self.assertEqual(confirmed["run"]["result"]["uiState"]["location"]["label"], "Coordinate 50.825351, -0.125125")

    def test_follow_up_uses_sidecar_session_memory(self):
        first = self.sidecar.invoke(
            {
                "message": "I want to visit Greenacre Solar Farm tomorrow for a survey. Please prepare a pre-visit RAMS-style review pack.",
                "useBedrock": False,
            }
        )
        follow_up = self.sidecar.invoke(
            {
                "sessionId": first["run"]["sessionId"],
                "message": "What do you mean",
                "useBedrock": False,
            }
        )

        self.assertEqual(follow_up["action"], "answered_from_memory")
        self.assertEqual(follow_up["route"], "follow_up")
        self.assertNotIn("review pack for What do you mean", follow_up["assistantMessage"])


if __name__ == "__main__":
    unittest.main()
