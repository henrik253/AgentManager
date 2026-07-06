from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any, Mapping
import tomllib


CONFIG_FILENAMES = ("agent-manager.local.toml", "agent-manager.toml")
DEFAULT_CONFIG_PATH = Path("agent-manager.toml")
EXAMPLE_CONFIG_PATH = Path("config/agent-manager.example.toml")
ENV_PREFIX = "AGENT_MANAGER_"


class ConfigError(ValueError):
    def __init__(self, field: str, message: str) -> None:
        super().__init__(f"{field}: {message}")
        self.field = field
        self.message = message


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
    source_path: Path | None = None


def load_config(
    path: Path | str | None = None,
    *,
    start: Path | str | None = None,
    env: Mapping[str, str] | None = None,
) -> AppConfig:
    env = os.environ if env is None else env
    config_path = resolve_config_path(path, start=start, env=env)
    data: dict[str, Any] = {}

    if config_path is not None:
        try:
            with config_path.open("rb") as config_file:
                loaded = tomllib.load(config_file)
        except OSError as exc:
            raise ConfigError("config", f"could not read {config_path}: {exc}") from exc
        except tomllib.TOMLDecodeError as exc:
            raise ConfigError("config", f"invalid TOML in {config_path}: {exc}") from exc
        if not isinstance(loaded, dict):
            raise ConfigError("config", "root must be a TOML table")
        data = loaded

    config = parse_config_data(data, source_path=config_path)
    return apply_env_overrides(config, env)


def resolve_config_path(
    path: Path | str | None = None,
    *,
    start: Path | str | None = None,
    env: Mapping[str, str] | None = None,
) -> Path | None:
    env = os.environ if env is None else env

    explicit = path or env.get(f"{ENV_PREFIX}CONFIG")
    if explicit is not None:
        explicit_path = Path(explicit)
        if not explicit_path.exists():
            raise ConfigError("config", f"file does not exist: {explicit_path}")
        if not explicit_path.is_file():
            raise ConfigError("config", f"path is not a file: {explicit_path}")
        return explicit_path

    return find_project_config(Path(start or Path.cwd()))


def find_project_config(start: Path) -> Path | None:
    current = start.resolve()
    if current.is_file():
        current = current.parent

    for directory in (current, *current.parents):
        for filename in CONFIG_FILENAMES:
            candidate = directory / filename
            if candidate.is_file():
                return candidate

    if EXAMPLE_CONFIG_PATH.is_file():
        return EXAMPLE_CONFIG_PATH
    return None


def parse_config_data(data: Mapping[str, Any], source_path: Path | None = None) -> AppConfig:
    if not isinstance(data, Mapping):
        raise ConfigError("config", "root must be a table")

    server_data = get_table(data, "server")
    workspace_data = get_table(data, "workspace")
    routing_data = get_table(data, "routing")
    backends_data = data.get("backends", [])

    return AppConfig(
        server=parse_server_config(server_data),
        workspace=parse_workspace_config(workspace_data),
        routing=parse_routing_config(routing_data),
        backends=parse_backend_configs(backends_data),
        source_path=source_path,
    )


def get_table(data: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = data.get(key, {})
    if not isinstance(value, Mapping):
        raise ConfigError(key, "must be a table")
    return value


def parse_server_config(data: Mapping[str, Any]) -> ServerConfig:
    websocket_path = parse_string(
        data.get("websocket_path", ServerConfig.websocket_path),
        "server.websocket_path",
        required=True,
    )
    if not websocket_path.startswith("/"):
        raise ConfigError("server.websocket_path", "must start with '/'")

    port = parse_int(data.get("port", ServerConfig.port), "server.port", minimum=1)
    if port > 65535:
        raise ConfigError("server.port", "must be less than or equal to 65535")

    return ServerConfig(
        host=parse_string(data.get("host", ServerConfig.host), "server.host", required=True),
        port=port,
        websocket_path=websocket_path,
        max_message_size=parse_int(
            data.get("max_message_size", ServerConfig.max_message_size),
            "server.max_message_size",
            minimum=1,
        ),
    )


def parse_workspace_config(data: Mapping[str, Any]) -> WorkspaceConfig:
    worktree_root = parse_string(
        data.get("worktree_root", WorkspaceConfig.worktree_root),
        "workspace.worktree_root",
        required=True,
    )
    branch_prefix = parse_string(
        data.get("branch_prefix", WorkspaceConfig.branch_prefix),
        "workspace.branch_prefix",
        required=True,
    )
    if Path(worktree_root).is_absolute():
        raise ConfigError("workspace.worktree_root", "must be a project-relative path")
    if ".." in Path(worktree_root).parts:
        raise ConfigError("workspace.worktree_root", "must not contain '..'")
    if any(char.isspace() for char in branch_prefix):
        raise ConfigError("workspace.branch_prefix", "must not contain whitespace")

    return WorkspaceConfig(
        worktree_root=worktree_root,
        branch_prefix=branch_prefix,
        allow_existing_worktree=parse_bool(
            data.get("allow_existing_worktree", WorkspaceConfig.allow_existing_worktree),
            "workspace.allow_existing_worktree",
        ),
    )


def parse_routing_config(data: Mapping[str, Any]) -> RoutingConfig:
    mode = parse_string(data.get("mode", RoutingConfig.mode), "routing.mode", required=True)
    if mode not in {"automatic", "explicit"}:
        raise ConfigError("routing.mode", "must be automatic or explicit")

    preferred_backends = parse_string_tuple(
        data.get("preferred_backends", RoutingConfig.preferred_backends),
        "routing.preferred_backends",
    )
    default_backend = parse_optional_string(
        data.get("default_backend"),
        "routing.default_backend",
    )

    return RoutingConfig(
        mode=mode,
        preferred_backends=preferred_backends,
        allow_fallback=parse_bool(
            data.get("allow_fallback", RoutingConfig.allow_fallback),
            "routing.allow_fallback",
        ),
        default_backend=default_backend,
    )


def parse_backend_configs(data: Any) -> tuple[BackendConfig, ...]:
    if not isinstance(data, list):
        raise ConfigError("backends", "must be an array of tables")

    backends = []
    seen_ids: set[str] = set()
    for index, backend_data in enumerate(data):
        field = f"backends[{index}]"
        if not isinstance(backend_data, Mapping):
            raise ConfigError(field, "must be a table")

        backend_id = parse_string(backend_data.get("id"), f"{field}.id", required=True)
        if backend_id in seen_ids:
            raise ConfigError(f"{field}.id", f"duplicate backend id: {backend_id}")
        seen_ids.add(backend_id)

        command = parse_string(
            backend_data.get("command"),
            f"{field}.command",
            required=True,
        )
        args = parse_string_tuple(backend_data.get("args", ()), f"{field}.args")

        backends.append(
            BackendConfig(
                id=backend_id,
                display_name=parse_optional_string(
                    backend_data.get("display_name"),
                    f"{field}.display_name",
                )
                or backend_id,
                command=command,
                enabled=parse_bool(
                    backend_data.get("enabled", BackendConfig.enabled),
                    f"{field}.enabled",
                ),
                args=args,
            )
        )

    return tuple(backends)


def apply_env_overrides(config: AppConfig, env: Mapping[str, str]) -> AppConfig:
    server = ServerConfig(
        host=env.get(f"{ENV_PREFIX}HOST", config.server.host),
        port=parse_int(
            env.get(f"{ENV_PREFIX}PORT", config.server.port),
            f"{ENV_PREFIX}PORT",
            minimum=1,
        ),
        websocket_path=env.get(
            f"{ENV_PREFIX}WEBSOCKET_PATH",
            config.server.websocket_path,
        ),
        max_message_size=parse_int(
            env.get(f"{ENV_PREFIX}MAX_MESSAGE_SIZE", config.server.max_message_size),
            f"{ENV_PREFIX}MAX_MESSAGE_SIZE",
            minimum=1,
        ),
    )
    if not server.websocket_path.startswith("/"):
        raise ConfigError(f"{ENV_PREFIX}WEBSOCKET_PATH", "must start with '/'")

    workspace = WorkspaceConfig(
        worktree_root=env.get(
            f"{ENV_PREFIX}WORKTREE_ROOT",
            config.workspace.worktree_root,
        ),
        branch_prefix=env.get(
            f"{ENV_PREFIX}BRANCH_PREFIX",
            config.workspace.branch_prefix,
        ),
        allow_existing_worktree=parse_bool(
            env.get(
                f"{ENV_PREFIX}ALLOW_EXISTING_WORKTREE",
                config.workspace.allow_existing_worktree,
            ),
            f"{ENV_PREFIX}ALLOW_EXISTING_WORKTREE",
        ),
    )
    validate_workspace_config(workspace)

    routing = RoutingConfig(
        mode=env.get(f"{ENV_PREFIX}ROUTING_MODE", config.routing.mode),
        preferred_backends=parse_env_string_tuple(
            env.get(f"{ENV_PREFIX}PREFERRED_BACKENDS"),
            config.routing.preferred_backends,
        ),
        allow_fallback=parse_bool(
            env.get(f"{ENV_PREFIX}ALLOW_FALLBACK", config.routing.allow_fallback),
            f"{ENV_PREFIX}ALLOW_FALLBACK",
        ),
        default_backend=env.get(
            f"{ENV_PREFIX}DEFAULT_BACKEND",
            config.routing.default_backend,
        ),
    )
    if routing.mode not in {"automatic", "explicit"}:
        raise ConfigError(f"{ENV_PREFIX}ROUTING_MODE", "must be automatic or explicit")

    backends = tuple(apply_backend_env_overrides(backend, env) for backend in config.backends)
    return AppConfig(
        server=server,
        workspace=workspace,
        routing=routing,
        backends=backends,
        source_path=config.source_path,
    )


def apply_backend_env_overrides(
    backend: BackendConfig,
    env: Mapping[str, str],
) -> BackendConfig:
    key_id = backend.id.upper().replace("-", "_")
    command = env.get(f"{ENV_PREFIX}BACKEND_{key_id}_COMMAND", backend.command)
    if isinstance(command, str) and not command.strip():
        raise ConfigError(f"{ENV_PREFIX}BACKEND_{key_id}_COMMAND", "must not be empty")
    enabled = parse_bool(
        env.get(f"{ENV_PREFIX}BACKEND_{key_id}_ENABLED", backend.enabled),
        f"{ENV_PREFIX}BACKEND_{key_id}_ENABLED",
    )
    args = parse_env_string_tuple(
        env.get(f"{ENV_PREFIX}BACKEND_{key_id}_ARGS"),
        backend.args,
    )
    return BackendConfig(
        id=backend.id,
        display_name=backend.display_name,
        command=command.strip() if isinstance(command, str) else command,
        enabled=enabled,
        args=args,
    )


def validate_workspace_config(workspace: WorkspaceConfig) -> None:
    if Path(workspace.worktree_root).is_absolute():
        raise ConfigError(f"{ENV_PREFIX}WORKTREE_ROOT", "must be a project-relative path")
    if ".." in Path(workspace.worktree_root).parts:
        raise ConfigError(f"{ENV_PREFIX}WORKTREE_ROOT", "must not contain '..'")
    if not workspace.branch_prefix:
        raise ConfigError(f"{ENV_PREFIX}BRANCH_PREFIX", "must not be empty")
    if any(char.isspace() for char in workspace.branch_prefix):
        raise ConfigError(f"{ENV_PREFIX}BRANCH_PREFIX", "must not contain whitespace")


def parse_string(value: Any, field: str, *, required: bool = False) -> str:
    if value is None:
        if required:
            raise ConfigError(field, "is required")
        return ""
    if not isinstance(value, str):
        raise ConfigError(field, "must be a string")
    stripped = value.strip()
    if required and not stripped:
        raise ConfigError(field, "must not be empty")
    return stripped


def parse_optional_string(value: Any, field: str) -> str | None:
    if value is None:
        return None
    parsed = parse_string(value, field)
    return parsed or None


def parse_string_tuple(value: Any, field: str) -> tuple[str, ...]:
    if value in (None, ""):
        return ()
    if not isinstance(value, list | tuple):
        raise ConfigError(field, "must be a list of strings")
    parsed = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise ConfigError(f"{field}[{index}]", "must be a non-empty string")
        parsed.append(item.strip())
    return tuple(parsed)


def parse_env_string_tuple(value: str | None, default: tuple[str, ...]) -> tuple[str, ...]:
    if value is None:
        return default
    if not value.strip():
        return ()
    return tuple(item.strip() for item in value.split(",") if item.strip())


def parse_bool(value: Any, field: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    raise ConfigError(field, "must be a boolean")


def parse_int(value: Any, field: str, *, minimum: int | None = None) -> int:
    if isinstance(value, bool):
        raise ConfigError(field, "must be an integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ConfigError(field, "must be an integer") from exc
    if minimum is not None and parsed < minimum:
        raise ConfigError(field, f"must be greater than or equal to {minimum}")
    return parsed
