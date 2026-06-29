from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from .config import RuntimeConfig


ALLOWED_UPLOAD_TYPES = {"application/pdf", "image/png", "image/jpeg"}


def create_upload_target(
    *,
    session_id: str,
    filename: str,
    content_type: str,
    size_bytes: int | None,
    config: RuntimeConfig,
) -> dict[str, Any]:
    upload_id = f"upload-{uuid.uuid4().hex[:12]}"
    extension = _safe_extension(filename, content_type)
    metadata = {
        "uploadId": upload_id,
        "displayName": f"evidence-{upload_id}{extension}",
        "contentType": content_type,
        "sizeBytes": size_bytes,
        "status": "pending",
        "storageMode": "s3" if config.s3_upload_bucket else "local-mock",
        "retentionDays": config.upload_retention_days,
    }
    if content_type not in ALLOWED_UPLOAD_TYPES:
        return {**metadata, "status": "rejected", "reason": "Unsupported file type."}
    if size_bytes is not None and size_bytes > 10_000_000:
        return {**metadata, "status": "rejected", "reason": "File is larger than the 10 MB hosted MVP limit."}
    if not config.s3_upload_bucket:
        return {
            **metadata,
            "status": "mocked",
            "uploadUrl": f"local-mock://{session_id}/{upload_id}/evidence{extension}",
            "fields": {},
            "note": "S3_UPLOAD_BUCKET is not configured; upload metadata is tracked for local testing only.",
        }

    key = f"sessions/{session_id}/uploads/{upload_id}/evidence{extension}"
    try:
        import boto3

        client = boto3.client("s3", region_name=config.aws_region)
        url = client.generate_presigned_url(
            ClientMethod="put_object",
            Params={
                "Bucket": config.s3_upload_bucket,
                "Key": key,
                "ContentType": content_type,
                "ServerSideEncryption": "AES256",
            },
            ExpiresIn=900,
        )
        return {**metadata, "status": "ready", "uploadUrl": url, "s3Key": key, "fields": {}}
    except Exception as exc:
        return {
            **metadata,
            "status": "fallback",
            "reason": f"S3 presign failed; upload remains unavailable. {exc.__class__.__name__}",
        }


def _safe_extension(filename: str, content_type: str) -> str:
    by_type = {
        "application/pdf": ".pdf",
        "image/png": ".png",
        "image/jpeg": ".jpg",
    }
    suffix = Path(filename).suffix.lower()
    if suffix in {".pdf", ".png", ".jpg", ".jpeg"}:
        return ".jpg" if suffix == ".jpeg" else suffix
    return by_type.get(content_type, ".bin")
