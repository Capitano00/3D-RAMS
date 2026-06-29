from __future__ import annotations

import sys
import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from main import invoke_local, ping_local  # noqa: E402
from three_d_rams.agent import run_site_briefing  # noqa: E402


class AgentCoreInvocationTests(unittest.TestCase):
    def test_ping_local_reports_agentcore_service(self):
        self.assertEqual(ping_local(), {"status": "ok", "service": "3d-rams-agentcore"})

    def test_invocation_wraps_existing_run_contract(self):
        response = invoke_local(
            {
                "input": {
                    "fixturePack": "public-lambeth-thames",
                    "useBedrock": False,
                    "upstream": {"source": "ASI_ONE", "confirmedByUser": True},
                }
            }
        )

        output = response["output"]
        run = output["run"]
        self.assertEqual(output["reportStatus"], "review_required")
        self.assertEqual(output["workflowMode"], "cached_public_fixture")
        self.assertEqual(run["runtime"]["fixturePack"], "public-lambeth-thames")
        self.assertFalse(run["runtime"]["liveApiCalls"])
        self.assertTrue(run["safety"]["allowed"])
        self.assertGreaterEqual(len(run["trace"]), 9)

    def test_packaged_workflow_matches_existing_fixture_mode(self):
        result = run_site_briefing({"fixturePack": "public-lambeth-thames", "useBedrock": False})

        self.assertEqual(result["runtime"]["fixturePackMode"], "cached-public-fixture")
        self.assertEqual(result["scene"]["provider"], "cesium-local-cached-fixture")
        self.assertTrue(result["evidence"])


if __name__ == "__main__":
    unittest.main()
