from pathlib import Path

import pytest

from agent_manager.config import ConfigError, load_config, resolve_config_path


def test_load_config_parses_backends_and_workspace():
    config = load_config(Path("config/agent-manager.example.toml"))

    assert config.workspace.worktree_root == ".agent-manager/worktrees"
    assert [backend.id for backend in config.backends] == ["claude", "codex", "gemini"]
    assert config.backends[2].display_name == "Gemini CLI"
    assert config.backends[2].command == "gemini"


@pytest.mark.parametrize(
    "config_path",
    sorted(Path("config").glob("agent-manager*.toml")),
    ids=lambda path: path.name,
)
def test_checked_in_example_configs_are_valid(config_path):
    config = load_config(config_path, env={})

    assert config.server.websocket_path.startswith("/")


def test_load_config_discovers_project_local_config(tmp_path):
    config_path = tmp_path / "agent-manager.toml"
    config_path.write_text(
        """
[server]
port = 9000

[[backends]]
id = "codex"
command = "codex"
""",
        encoding="utf-8",
    )
    nested = tmp_path / "src" / "pkg"
    nested.mkdir(parents=True)

    config = load_config(start=nested, env={})

    assert config.source_path == config_path
    assert config.server.port == 9000
    assert [backend.id for backend in config.backends] == ["codex"]


def test_local_config_takes_precedence_over_shared_config(tmp_path):
    (tmp_path / "agent-manager.toml").write_text(
        """
[server]
port = 9000
""",
        encoding="utf-8",
    )
    local_path = tmp_path / "agent-manager.local.toml"
    local_path.write_text(
        """
[server]
port = 9100
""",
        encoding="utf-8",
    )

    assert resolve_config_path(start=tmp_path, env={}) == local_path


def test_environment_overrides_runtime_settings(tmp_path):
    config_path = tmp_path / "agent-manager.toml"
    config_path.write_text(
        """
[routing]
preferred_backends = ["claude"]

[[backends]]
id = "claude"
command = "claude"
""",
        encoding="utf-8",
    )

    config = load_config(
        config_path,
        env={
            "AGENT_MANAGER_PORT": "9999",
            "AGENT_MANAGER_WEBSOCKET_PATH": "/custom/session",
            "AGENT_MANAGER_PREFERRED_BACKENDS": "codex,gemini",
            "AGENT_MANAGER_BACKEND_CLAUDE_COMMAND": "/usr/local/bin/claude",
            "AGENT_MANAGER_ALLOW_EXISTING_WORKTREE": "true",
        },
    )

    assert config.server.port == 9999
    assert config.server.websocket_path == "/custom/session"
    assert config.routing.preferred_backends == ("codex", "gemini")
    assert config.backends[0].command == "/usr/local/bin/claude"
    assert config.workspace.allow_existing_worktree


def test_validation_errors_include_field_path(tmp_path):
    config_path = tmp_path / "agent-manager.toml"
    config_path.write_text(
        """
[server]
port = "not-a-port"
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="server.port"):
        load_config(config_path, env={})
