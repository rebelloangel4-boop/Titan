"""Shared application services for the legacy HTTP API and the FastAPI/ASGI adapter.

This layer deliberately delegates to the existing SQLite store, Workspace and ToolRegistry.
It does not introduce a second queue, memory engine or artifact store.
"""
import json
import time

from .providers import Router
from .tools import ToolRegistry
from .security import (
    create_approval_challenge,
    register_device_public_key,
    verify_approval_signature,
)


class APIService:
    def __init__(self, db, workspace=None):
        from .workspace import Workspace
        self.db = db
        self.workspace = workspace or Workspace(db)

    def list_missions(self):
        return self.db.list()

    def create_mission(self, data):
        if not isinstance(data, dict):
            raise ValueError("Mission body must be an object")
        objective = data.get("objective")
        kind = data.get("kind", "debate")
        payload = data.get("payload", {})
        if not isinstance(payload, dict):
            raise ValueError("Payload must be an object")
        if kind == "debate" and "providers" in payload:
            from .core import PROVIDERS
            providers = payload["providers"]
            if (not isinstance(providers, list) or not 2 <= len(providers) <= 7
                    or any(p not in {*PROVIDERS, "local"} for p in providers)
                    or len(set(providers)) != len(providers)):
                raise ValueError("Select 2–7 distinct known providers")
        if kind == "tool" and payload.get("tool") not in ToolRegistry.names:
            raise ValueError("Unsupported tool")
        due = data.get("due")
        if due is not None and (not isinstance(due, (int, float)) or isinstance(due, bool)
                                or not time.time() - 1 <= due <= time.time() + 31536000):
            raise ValueError("Schedule must be within one year")
        project = data.get("project", "default")
        mid = self.db.submit(
            objective, kind, json.loads(self._redact(json.dumps(payload))),
            due, project=project,
        )
        return {"id": mid}

    @staticmethod
    def _redact(value):
        from .security import redact
        return redact(value)

    def control_mission(self, mission_id, action):
        self.db.control(mission_id, action)
        return self.db.get(mission_id)

    def get_debate(self, mission_id):
        mission = self.db.get(mission_id)
        if not mission or mission.get("kind") != "debate":
            raise KeyError(mission_id)
        return mission

    def pending_approvals(self):
        with self.db.connect() as c:
            return [dict(r) for r in c.execute(
                "SELECT * FROM approvals WHERE status='pending' ORDER BY created DESC LIMIT 100"
            )]

    def register_device(self, device_id, algorithm, public_key):
        return register_device_public_key(self.db, device_id, algorithm, public_key)

    def approval_challenge(self, approval_id, device_id):
        return create_approval_challenge(self.db, approval_id, device_id)

    def approve_signed(self, device_id, approval_id, action_digest, expiry, nonce, signature):
        return verify_approval_signature(
            self.db, device_id, approval_id, action_digest, expiry, nonce, signature
        )

    def list_artifacts(self, project=None):
        return self.workspace.artifacts(project)

    def read_artifact(self, artifact_id):
        return self.workspace.read_artifact(artifact_id)

    def state(self):
        with self.db.connect() as c:
            used = dict(c.execute(
                "SELECT COUNT(*) calls,COALESCE(SUM(cost),0) reserved_usd FROM calls WHERE ts>=?",
                (int(time.time() // 86400) * 86400,),
            ).fetchone())
        return {
            "missions": self.list_missions(),
            "models": Router(self.db).catalog(),
            "metrics": Router(self.db).metrics(),
            "memory": self.db.memories(),
            "events": self.db.events(),
            "approvals": self.pending_approvals(),
            "budget": {
                "daily_usd": float(__import__("os").getenv("TITAN_DAILY_USD", "0")),
                "daily_calls": int(__import__("os").getenv("TITAN_DAILY_CALLS", "50")),
                **used,
            },
            "tools": sorted(ToolRegistry.names),
            "projects": self.workspace.projects(),
            "artifacts": self.list_artifacts(),
            "schedules": self.workspace.schedules(),
            "runtime": "single-operator; live providers require credentials",
        }
