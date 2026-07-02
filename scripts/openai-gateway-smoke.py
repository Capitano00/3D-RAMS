from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENTCORE_APP = ROOT / "app" / "rams_supervisor_runtime"
AGENT_TOOLS_APP = ROOT / "app" / "rams_agent_tools"
sys.path.insert(0, str(AGENT_TOOLS_APP))
sys.path.insert(0, str(AGENTCORE_APP))

from supervisor_core.agent import run_site_briefing  # noqa: E402


def main() -> int:
    if not os.getenv("OPENAI_BASE_URL") or not os.getenv("OPENAI_API_KEY"):
        print("Set OPENAI_BASE_URL and OPENAI_API_KEY for the OpenAI-compatible gateway smoke.", file=sys.stderr)
        return 2

    os.environ.setdefault("ENABLE_LIVE_MODEL", "true")
    os.environ.setdefault("RAMS_LLM_PROVIDER", "openai")
    os.environ.setdefault("OPENAI_MODEL", "gpt-5.4-mini")

    result = run_site_briefing({"useBedrock": True, "goal": "OpenAI-compatible gateway smoke test briefing"})
    model_step = next(step for step in result["trace"] if step["name"] == "generate_bedrock_briefing")
    runtime = result["runtime"]
    summary = {
        "runtime": runtime,
        "modelStepStatus": model_step["status"],
        "modelStepOutput": model_step["output"],
        "headline": result["briefing"]["headline"],
        "safety": result["safety"]["level"],
    }
    print(json.dumps(summary, indent=2))
    return 0 if runtime.get("modelProvider") == "openai-compatible" and model_step["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
