from __future__ import annotations

from fastapi import FastAPI, Header
from fastapi.middleware.cors import CORSMiddleware

from .access import validate_access_code
from .agent import run_site_briefing
from .chat_agent import run_fieldbrief_chat
from .config import RuntimeConfig
from .models import ChatRequest, HealthResponse, SessionStartRequest, SiteBriefRequest, UploadUrlRequest
from .session_store import create_session, get_session, public_session
from .upload_service import create_upload_target


app = FastAPI(title="3D-RAMS Hosted Pre-Visit Agent API", version="0.2.0")
_startup_config = RuntimeConfig.from_env(request_bedrock=False)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_startup_config.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
def health() -> dict[str, str]:
    return {"status": "ok", "service": "3d-rams-demo1"}


@app.post("/api/run")
def run_agent(payload: SiteBriefRequest, x_3drams_access: str | None = Header(default=None)) -> dict[str, object]:
    config = RuntimeConfig.from_env(request_bedrock=payload.useBedrock)
    if config.app_access_token_hash:
        validate_access_code(x_3drams_access, config)
    return run_site_briefing(payload.to_agent_request())


@app.post("/api/session/start")
def start_session(payload: SessionStartRequest) -> dict[str, object]:
    config = RuntimeConfig.from_env(request_bedrock=False)
    access_label = validate_access_code(payload.accessCode, config)
    session = create_session(tester_alias=payload.testerAlias, access_label=access_label, config=config)
    return {
        "sessionId": session["sessionId"],
        "testerAlias": session.get("testerAlias"),
        "accessLabel": session.get("accessLabel"),
        "runtime": {
            "hostedProductMode": True,
            "accessMode": "shared-code" if config.app_access_token_hash else "local-dev-open",
            "sessionTraceMode": session.get("storageMode", "memory"),
        },
    }


@app.post("/api/upload-url")
def create_upload_url(payload: UploadUrlRequest) -> dict[str, object]:
    config = RuntimeConfig.from_env(request_bedrock=False)
    get_session(payload.sessionId, config)
    upload = create_upload_target(
        session_id=payload.sessionId,
        filename=payload.filename,
        content_type=payload.contentType,
        size_bytes=payload.sizeBytes,
        config=config,
    )
    from .session_store import add_upload

    add_upload(payload.sessionId, upload, config)
    return upload


@app.post("/api/chat")
def chat(payload: ChatRequest) -> dict[str, object]:
    config = RuntimeConfig.from_env(request_bedrock=payload.useBedrock)
    get_session(payload.sessionId, config)
    return run_fieldbrief_chat(
        session_id=payload.sessionId,
        message=payload.message,
        uploaded_file_ids=payload.uploadedFileIds,
        use_bedrock=payload.useBedrock,
        config=config,
    )


@app.get("/api/session/{session_id}")
def read_session(session_id: str) -> dict[str, object]:
    config = RuntimeConfig.from_env(request_bedrock=False)
    return public_session(get_session(session_id, config))
