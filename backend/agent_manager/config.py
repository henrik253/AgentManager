from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import tomllib


DEFAULT_CONFIG_PATH = Path("config/agent-manager.example.toml")


@dataclass(frozen=True)
class ServerConfig:
    host: str = "127.0.0.1"
    port: int = 8765
    websocket_path: str = "/v1/session"
    max_message_size: int = 1_048_576


@dataclass(frozen=True)
class WorkspaceConfig:
    worktree_root: str = ".agent-manager/worktrees"
    branch_prefix: str = "agent-task/"
    allow_existing_worktree: bool = False


@dataclass(frozen=True)
class RoutingConfig:
    mode: str = "automatic"
    preferred_backends: tuple[str, ...] = ()
    allow_fallback: bool = True
    default_backend: str | None = None


@dataclass(frozen=True)
class BackendConfig:
    id: str
    display_name: str | None = None
    command: str | None = None
    enabled: bool = True
    args: tuple[str, ...] = ()


@dataclass(frozen=True)
class AppConfig:
    server: ServerConfig = ServerConfig()
    workspace: WorkspaceConfig = WorkspaceConfig()
    routing: RoutingConfig = RoutingConfig()
    backends: tuple[BackendConfig, ...] = ()


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> AppConfig:
    if not path.exists():
        return AppConfig()

    with path.open("rb") as config_file:
        data = tomllib.load(config_file)

    server_data = data.get("server", {})
    workspace_data = data.get("workspace", {})
    routing_data = data.get("routing", {})
    backends_data = data.get("backends", [])
    websocket_path = str(server_data.get("websocket_path", ServerConfig.websocket_path))
    if not websocket_path.startswith("/"):
        raise ValueError("server.websocket_path must start with '/'")

    return AppConfig(
        server=ServerConfig(
            host=str(server_data.get("host", ServerConfig.host)),
            port=int(server_data.get("port", ServerConfig.port)),
            websocket_path=websocket_path,
            max_message_size=int(
                server_data.get("max_message_size", ServerConfig.max_message_size)
            ),
        ),
        workspace=WorkspaceConfig(
            worktree_root=str(
                workspace_data.get("worktree_root", WorkspaceConfig.worktree_root)
            ),
            branch_prefix=str(
                workspace_data.get("branch_prefix", WorkspaceConfig.branch_prefix)
            ),
            allow_existing_worktree=bool(
                workspace_data.get(
                    "allow_existing_worktree",
                    WorkspaceConfig.allow_existing_worktree,
                )
            ),
        ),
        routing=parse_routing_config(routing_data),
        backends=parse_backend_configs(backends_data),
    )


def parse_routing_config(data: Any) -> RoutingConfig:
    if not isinstance(data, dict):
        raise ValueError("routing must be a table")

    mode = str(data.get("mode", RoutingConfig.mode))
    if mode not in {"automatic", "explicit"}:
        raise ValueError("routing.mode must be automatic or explicit")

    preferred_backends = data.get("preferred_backends", RoutingConfig.preferred_backends)
    if not isinstance(preferred_backends, list | tuple) or not all(
        isinstance(backend_id, str) and backend_id for backend_id in preferred_backends
    ):
        raise ValueError("routing.preferred_backends must be a list of backend ids")

    default_backend = data.get("default_backend")
    if default_backend is not None and (
        not isinstance(default_backend, str) or not default_backend
    ):
        raise ValueError("routing.default_backend must be a backend id when provided")

    return RoutingConfig(
        mode=mode,
        preferred_backends=tuple(preferred_backends),
        allow_fallback=bool(data.get("allow_fallback", RoutingConfig.allow_fallback)),
        default_backend=default_backend,
    )


def parse_backend_configs(data: Any) -> tuple[BackendConfig, ...]:
    if not isinstance(data, list):
        raise ValueError("backends must be an array of tables")

    backends = []
    seen_ids: set[str] = set()
    for backend_data in data:
        if not isinstance(backend_data, dict):
            raise ValueError("each backend entry must be a table")

        backend_id = str(backend_data.get("id", "")).strip()
        if not backend_id:
            raise ValueError("backend.id is required")
        if backend_id in seen_ids:
            raise ValueError(f"duplicate backend id: {backend_id}")
        seen_ids.add(backend_id)

        display_name = backend_data.get("display_name")
        if display_name is not None and not isinstance(display_name, str):
            raise ValueError("backend.display_name must be a string when provided")

        command = backend_data.get("command")
        if not isinstance(command, str) or not command.strip():
            raise ValueError(f"backend.command is required for {backend_id}")

        args = backend_data.get("args", [])
        if not isinstance(args, list) or not all(isinstance(arg, str) for arg in args):
            raise ValueError(f"backend.args must be an array of strings for {backend_id}")

        backends.append(
            BackendConfig(
                id=backend_id,
                display_name=display_name or backend_id,
                command=command.strip(),
                enabled=bool(backend_data.get("enabled", BackendConfig.enabled)),
                args=tuple(args),
            )
        )

    return tuple(backends)
