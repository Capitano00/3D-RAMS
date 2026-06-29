from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "fixtures"
ALLOWED_FIXTURE_PACKS = {"public-lambeth-thames"}


def load_json(name: str) -> dict[str, Any]:
    with (FIXTURES / name).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_text(name: str) -> str:
    with (FIXTURES / name).open("r", encoding="utf-8") as handle:
        return handle.read()


def load_fixture_pack(name: str | None) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if not name:
        return None, None

    safe_name = name.strip().lower()
    if not safe_name:
        return None, None

    if safe_name not in ALLOWED_FIXTURE_PACKS:
        return None, {
            "requested": name,
            "status": "fallback",
            "reason": f"Fixture pack '{name}' is not allowed; synthetic defaults were used.",
        }

    pack_dir = FIXTURES / safe_name
    fixtures_root = FIXTURES.resolve()
    resolved_pack_dir = pack_dir.resolve()
    if not resolved_pack_dir.is_relative_to(fixtures_root):
        return None, {
            "requested": name,
            "status": "fallback",
            "reason": f"Fixture pack '{name}' was outside the fixture boundary; synthetic defaults were used.",
        }

    pack_file = pack_dir / "pack.json"
    if not pack_file.exists():
        return None, {
            "requested": name,
            "status": "fallback",
            "reason": f"Fixture pack '{name}' was not found; synthetic defaults were used.",
        }

    with pack_file.open("r", encoding="utf-8") as handle:
        pack = json.load(handle)

    planning_file = pack.get("planning", {}).get("file")
    if planning_file:
        planning_path = (pack_dir / planning_file).resolve()
        if planning_path.is_relative_to(resolved_pack_dir) and planning_path.exists():
            with planning_path.open("r", encoding="utf-8") as handle:
                pack["planning"]["text"] = handle.read()
        else:
            pack["planning"]["text"] = None
            pack.setdefault("warnings", []).append(
                f"Planning fixture file '{planning_file}' was missing from pack '{safe_name}'."
            )

    pack["name"] = safe_name
    return pack, None
