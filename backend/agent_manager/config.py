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
class AppConfig:
    server: ServerConfig = ServerConfig()


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> AppConfig:
    if not path.exists():
        return AppConfig()

    with path.open("rb") as config_file:
        data = tomllib.load(config_file)

    server_data = data.get("server", {})
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
        )
    )
