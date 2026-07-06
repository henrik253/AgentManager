from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
import json
from typing import Any
from uuid import uuid4


JsonObject = dict[str, Any]


@dataclass
class EventWriter:
    websocket: Any
    session_id: str = field(default_factory=lambda: str(uuid4()))
    sequence: int = 0

    async def send(self, event_type: str, **payload: Any) -> None:
        self.sequence += 1
        event = {
            "type": event_type,
            "session_id": self.session_id,
            "sequence": self.sequence,
            "timestamp": datetime.now(UTC).isoformat(),
            **payload,
        }
        await self.websocket.send(json.dumps(event, separators=(",", ":")))


def parse_client_message(raw_message: str | bytes) -> JsonObject:
    if isinstance(raw_message, bytes):
        raise ValueError("binary websocket messages are not supported")

    try:
        message = json.loads(raw_message)
    except json.JSONDecodeError as exc:
        raise ValueError("message must be valid JSON") from exc

    if not isinstance(message, dict):
        raise ValueError("message must be a JSON object")

    message_type = message.get("type")
    if not isinstance(message_type, str) or not message_type:
        raise ValueError("message.type is required")

    return message


def validate_prompt_submission(message: JsonObject) -> JsonObject:
    prompt = message.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("prompt.submit requires a non-empty prompt")

    backend = message.get("backend")
    if backend is not None and not isinstance(backend, str):
        raise ValueError("backend must be a string when provided")

    model = message.get("model")
    if model is not None and not isinstance(model, str):
        raise ValueError("model must be a string when provided")

    workspace = message.get("workspace")
    if workspace is not None:
        workspace = validate_workspace_hint(workspace)

    return {
        "prompt": prompt,
        "backend": backend,
        "model": model,
        "workspace": workspace,
    }


def validate_workspace_hint(workspace: Any) -> JsonObject:
    if not isinstance(workspace, dict):
        raise ValueError("workspace must be an object when provided")

    mode = workspace.get("mode")
    if mode is not None and mode not in {"create_worktree", "existing_worktree"}:
        raise ValueError("workspace.mode must be create_worktree or existing_worktree")

    branch = workspace.get("branch")
    if branch is not None and not isinstance(branch, str):
        raise ValueError("workspace.branch must be a string when provided")

    worktree_path = workspace.get("worktree_path")
    if worktree_path is not None and not isinstance(worktree_path, str):
        raise ValueError("workspace.worktree_path must be a string when provided")

    return {
        "mode": mode or "create_worktree",
        "branch": branch,
        "worktree_path": worktree_path,
    }
