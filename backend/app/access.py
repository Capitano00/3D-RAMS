from __future__ import annotations

import hashlib
import hmac

from fastapi import HTTPException

from .config import RuntimeConfig


def hash_access_code(access_code: str) -> str:
    return hashlib.sha256(access_code.encode("utf-8")).hexdigest()


def validate_access_code(access_code: str | None, config: RuntimeConfig) -> str:
    """Validate the shared tester code without exposing it in logs or responses."""
    if not config.app_access_token_hash:
        return "local-dev"
    if not access_code:
        raise HTTPException(status_code=401, detail="Access code required.")
    supplied_hash = hash_access_code(access_code.strip())
    if not hmac.compare_digest(supplied_hash, config.app_access_token_hash.strip().lower()):
        raise HTTPException(status_code=401, detail="Invalid access code.")
    return config.app_access_code_label
