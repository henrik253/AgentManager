from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
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
class AppConfig:
    server: ServerConfig = ServerConfig()
    workspace: WorkspaceConfig = WorkspaceConfig()


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> AppConfig:
    if not path.exists():
        return AppConfig()

    with path.open("rb") as config_file:
        data = tomllib.load(config_file)

    server_data = data.get("server", {})
    workspace_data = data.get("workspace", {})
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
    )
