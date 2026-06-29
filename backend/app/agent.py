from __future__ import annotations

import sys
from pathlib import Path


AGENTCORE_APP = Path(__file__).resolve().parents[2] / "app" / "rams_agentcore"
if str(AGENTCORE_APP) not in sys.path:
    sys.path.insert(0, str(AGENTCORE_APP))

from three_d_rams.agent import run_site_briefing  # noqa: E402,F401
