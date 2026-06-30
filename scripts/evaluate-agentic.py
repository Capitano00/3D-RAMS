from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
AGENTCORE_APP = ROOT / "app" / "rams_supervisor_runtime"
AGENT_TOOLS_APP = ROOT / "app" / "rams_agent_tools"
sys.path.insert(0, str(AGENT_TOOLS_APP))
sys.path.insert(0, str(AGENTCORE_APP))

from supervisor_core.agentcore_adapter import handle_invocation  # noqa: E402
from supervisor_core.agentic_eval import evaluate_agentic_output  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the external LLM-backed agentic evaluator.")
    parser.add_argument(
        "--input",
        type=Path,
        help="Optional JSON file containing an AgentCore invocation output or {run, structuredReport}.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "docs" / "evaluation-results" / "agentic-eval-latest.json",
        help="Path for the public-safe evaluation artifact.",
    )
    parser.add_argument("--fixture-pack", default="public-lambeth-thames")
    parser.add_argument("--use-bedrock", action="store_true")
    parser.add_argument("--fail-on-warn", action="store_true")
    args = parser.parse_args()

    payload = _load_or_generate_payload(args)
    artifact = evaluate_agentic_output(payload)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")

    print(
        f"agentic-eval {artifact['overall']['status']} "
        f"score={artifact['overall']['score']} artifact={args.output}"
    )
    for item in artifact["rubric"]:
        print(f"- {item['id']}: {item['status']} ({item['score']})")

    if artifact["overall"]["status"] == "fail":
        return 1
    if args.fail_on_warn and artifact["overall"]["status"] == "warn":
        return 1
    return 0


def _load_or_generate_payload(args: argparse.Namespace) -> dict[str, Any]:
    if args.input:
        return json.loads(args.input.read_text(encoding="utf-8"))

    return handle_invocation(
        {
            "input": {
                "fixturePack": args.fixture_pack,
                "useBedrock": args.use_bedrock,
            }
        }
    )


if __name__ == "__main__":
    raise SystemExit(main())
