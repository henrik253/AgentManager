from pathlib import Path

from agent_manager.config import load_config


def test_load_config_parses_backends_and_workspace():
    config = load_config(Path("config/agent-manager.example.toml"))

    assert config.workspace.worktree_root == ".agent-manager/worktrees"
    assert [backend.id for backend in config.backends] == ["claude", "codex", "gemini"]
    assert config.backends[2].display_name == "Gemini CLI"
    assert config.backends[2].command == "gemini"
