"""Authenticated FastAPI adapter for the existing TITAN Python engine.

Run with: uvicorn titan.asgi:create_app --factory --host 127.0.0.1 --port 8788
The existing stdlib server remains available and backward compatible.
"""
import asyncio
import os
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import Response, StreamingResponse

from .api_services import APIService
from .events import event_stream
from .security import authenticate
from .store import Database


def create_app(db=None, token=None):
    token = token if token is not None else os.getenv("TITAN_TOKEN", "")
    if not isinstance(token, str) or len(token) < 32:
        raise ValueError("TITAN_TOKEN must have at least 32 characters")
    db = db or Database(os.getenv("TITAN_DB", "titan.db"))
    service = APIService(db)
    app = FastAPI(title="TITAN API", version="0.1.0", docs_url=None, redoc_url=None)
    app.state.db = db
    app.state.service = service

    def require_auth(authorization: Optional[str] = Header(default=None)):
        if not authenticate(authorization, token):
            raise HTTPException(status_code=401, detail="Authentication required",
                                headers={"WWW-Authenticate": "Bearer"})
        return True

    def translate_error(exc):
        if isinstance(exc, KeyError):
            raise HTTPException(status_code=404, detail="Resource not found")
        if isinstance(exc, PermissionError):
            raise HTTPException(status_code=403, detail="Permission denied")
        if isinstance(exc, (ValueError, TypeError)):
            raise HTTPException(status_code=400, detail="Invalid request fields")
        raise exc

    @app.get("/healthz")
    async def healthz():
        return {"status": "ok"}

    @app.get("/api/state", dependencies=[Depends(require_auth)])
    async def state():
        return await asyncio.to_thread(service.state)

    @app.get("/api/missions", dependencies=[Depends(require_auth)])
    async def list_missions():
        return await asyncio.to_thread(service.list_missions)

    @app.post("/api/missions", status_code=201, dependencies=[Depends(require_auth)])
    async def create_mission(body: dict):
        try:
            return await asyncio.to_thread(service.create_mission, body)
        except (KeyError, ValueError, TypeError, PermissionError) as exc:
            translate_error(exc)

    @app.post("/api/missions/{mission_id}/control", dependencies=[Depends(require_auth)])
    async def control_mission(mission_id: str, body: dict):
        try:
            return await asyncio.to_thread(service.control_mission, mission_id, body["action"])
        except (KeyError, ValueError, TypeError, PermissionError) as exc:
            translate_error(exc)

    @app.get("/api/debates/{mission_id}", dependencies=[Depends(require_auth)])
    async def get_debate(mission_id: str):
        try:
            return await asyncio.to_thread(service.get_debate, mission_id)
        except (KeyError, ValueError, TypeError, PermissionError) as exc:
            translate_error(exc)

    @app.get("/api/approvals", dependencies=[Depends(require_auth)])
    async def pending_approvals():
        return await asyncio.to_thread(service.pending_approvals)

    @app.post("/api/devices/register", dependencies=[Depends(require_auth)])
    async def register_device(body: dict):
        enrollment = os.getenv("TITAN_DEVICE_ENROLLMENT_TOKEN", "")
        supplied = body.get("enrollment_token", "")
        import secrets
        if not enrollment or not secrets.compare_digest(str(supplied), enrollment):
            raise HTTPException(status_code=403, detail="Device enrollment is not enabled or token is invalid")
        try:
            return await asyncio.to_thread(service.register_device, body["device_id"], body["algorithm"], body["public_key"])
        except (KeyError, ValueError, TypeError, PermissionError) as exc:
            translate_error(exc)

    @app.post("/api/approvals/{approval_id}/challenge", dependencies=[Depends(require_auth)])
    async def approval_challenge(approval_id: str, body: dict):
        try:
            return await asyncio.to_thread(service.approval_challenge, approval_id, body["device_id"])
        except (KeyError, ValueError, TypeError, PermissionError) as exc:
            translate_error(exc)

    @app.post("/api/approvals/{approval_id}/verify", dependencies=[Depends(require_auth)])
    async def verify_approval(approval_id: str, body: dict):
        try:
            return await asyncio.to_thread(
                service.approve_signed, body["device_id"], approval_id,
                body["action_digest"], body["expiry"], body["nonce"], body["signature"],
            )
        except (KeyError, ValueError, TypeError, PermissionError) as exc:
            translate_error(exc)

    @app.get("/api/artifacts", dependencies=[Depends(require_auth)])
    async def list_artifacts(project: Optional[str] = None):
        return await asyncio.to_thread(service.list_artifacts, project)

    @app.get("/api/artifacts/{artifact_id}", dependencies=[Depends(require_auth)])
    async def read_artifact(artifact_id: str):
        try:
            metadata, raw = await asyncio.to_thread(service.read_artifact, artifact_id)
            return Response(raw, media_type=metadata.get("mime") or "application/octet-stream",
                            headers={"Content-Disposition": 'attachment; filename="' + metadata["name"] + '"',
                                     "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})
        except (KeyError, ValueError, TypeError, PermissionError) as exc:
            translate_error(exc)

    @app.get("/api/events", dependencies=[Depends(require_auth)])
    async def events(request: Request, last_event_id: Optional[str] = Header(default=None, alias="Last-Event-ID"),
                     job_id: Optional[str] = None):
        raw_cursor = last_event_id or "0"
        if not raw_cursor.isdigit():
            raise HTTPException(status_code=400, detail="Last-Event-ID must be a non-negative integer")
        cursor = int(raw_cursor)
        async def disconnected():
            return await request.is_disconnected()
        return StreamingResponse(
            event_stream(db, cursor=cursor, job_id=job_id, disconnected=disconnected),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache, no-transform",
                     "X-Accel-Buffering": "no", "Connection": "keep-alive"},
        )

    return app


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(create_app(), host=os.getenv("TITAN_HOST", "127.0.0.1"),
                port=int(os.getenv("TITAN_ASGI_PORT", "8788")))
