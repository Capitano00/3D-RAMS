from __future__ import annotations

import time
import uuid
from typing import Any

from fastapi import HTTPException

from .config import RuntimeConfig


_SESSIONS: dict[str, dict[str, Any]] = {}


def create_session(*, tester_alias: str | None, access_label: str, config: RuntimeConfig) -> dict[str, Any]:
    now = _now_iso()
    session = {
        "sessionId": f"session-{uuid.uuid4().hex[:16]}",
        "testerAlias": tester_alias,
        "accessLabel": access_label,
        "createdAt": now,
        "updatedAt": now,
        "runs": [],
        "uploads": [],
        "storageMode": "memory",
    }
    if config.dynamodb_session_table:
        session["storageMode"] = "dynamodb" if _write_dynamodb_session(session, config) else "memory-fallback"
    _SESSIONS[session["sessionId"]] = session
    return session


def get_session(session_id: str, config: RuntimeConfig | None = None) -> dict[str, Any]:
    session = _SESSIONS.get(session_id)
    if not session and config and config.dynamodb_session_table:
        session = _read_dynamodb_session(session_id, config)
        if session:
            _SESSIONS[session_id] = session
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or expired.")
    return session


def add_upload(session_id: str, upload: dict[str, Any], config: RuntimeConfig) -> None:
    session = get_session(session_id, config)
    session["uploads"].append(upload)
    session["updatedAt"] = _now_iso()
    _persist_session(session, config)


def add_run(session_id: str, run_summary: dict[str, Any], config: RuntimeConfig) -> None:
    session = get_session(session_id, config)
    session["runs"].append(run_summary)
    session["updatedAt"] = _now_iso()
    _persist_session(session, config)


def public_session(session: dict[str, Any]) -> dict[str, Any]:
    return {
        "sessionId": session["sessionId"],
        "testerAlias": session.get("testerAlias"),
        "accessLabel": session.get("accessLabel"),
        "createdAt": session.get("createdAt"),
        "updatedAt": session.get("updatedAt"),
        "runs": session.get("runs", []),
        "uploads": session.get("uploads", []),
        "storageMode": session.get("storageMode", "memory"),
    }


def _persist_session(session: dict[str, Any], config: RuntimeConfig) -> None:
    if not config.dynamodb_session_table:
        return
    if _write_dynamodb_session(session, config):
        session["storageMode"] = "dynamodb"
    elif session.get("storageMode") == "dynamodb":
        session["storageMode"] = "memory-fallback"


def _write_dynamodb_session(session: dict[str, Any], config: RuntimeConfig) -> bool:
    """Write session trace to DynamoDB when configured; memory remains fallback."""
    if not config.dynamodb_session_table:
        return False
    try:
        import boto3

        resource = boto3.resource("dynamodb", region_name=config.aws_region)
        table = resource.Table(config.dynamodb_session_table)
        table.put_item(Item=session)
        return True
    except Exception:
        return False


def _read_dynamodb_session(session_id: str, config: RuntimeConfig) -> dict[str, Any] | None:
    if not config.dynamodb_session_table:
        return None
    try:
        import boto3

        resource = boto3.resource("dynamodb", region_name=config.aws_region)
        table = resource.Table(config.dynamodb_session_table)
        response = table.get_item(Key={"sessionId": session_id})
        item = response.get("Item")
        return item if isinstance(item, dict) else None
    except Exception:
        return None


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
