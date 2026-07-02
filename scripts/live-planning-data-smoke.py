#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "app" / "rams_agent_tools", ROOT / "app" / "rams_supervisor_runtime"):
    sys.path.insert(0, str(path))

from supervisor_core.agent import run_site_briefing  # noqa: E402


def main() -> int:
    if os.getenv("ENABLE_LIVE_PLANNING_DATA", "").strip().lower() not in {"1", "true", "yes", "on"}:
        print("skipped: set ENABLE_LIVE_PLANNING_DATA=true to run the live Planning Data smoke")
        return 0

    result = run_site_briefing(
        {
            "siteName": "Live Planning Data smoke coordinate",
            "latitude": 51.5074,
            "longitude": -0.1278,
            "locationConfirmation": {"status": "confirmed"},
            "useBedrock": False,
        }
    )
    planning_data = result["runtime"]["planningData"]
    print(json.dumps(planning_data, indent=2, sort_keys=True))
    if not planning_data.get("liveCallAttempted"):
        print("failed: live Planning Data lookup was not attempted", file=sys.stderr)
        return 1
    if planning_data.get("status") not in {"live", "partial"}:
        print(f"failed: unexpected Planning Data status {planning_data.get('status')}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
