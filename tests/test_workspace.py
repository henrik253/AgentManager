import asyncio
import subprocess
from pathlib import Path

import pytest

from agent_manager.config import AppConfig, WorkspaceConfig
from agent_manager.workspace import WorkspaceResolutionError, resolve_task_workspace


def test_create_worktree_creates_git_worktree_under_configured_root(tmp_path):
    repo = create_git_repo(tmp_path / "repo")
    config = AppConfig(
        workspace=WorkspaceConfig(worktree_root=".agent-manager/worktrees"),
        source_path=repo / "agent-manager.toml",
    )

    async def scenario():
        resolved = await resolve_task_workspace(
            config,
            {"mode": "create_worktree", "branch": "agent-task/test-worktree"},
            session_id="session-123",
        )

        assert resolved.mode == "create_worktree"
        assert resolved.branch == "agent-task/test-worktree"
        assert resolved.path == repo / ".agent-manager" / "worktrees" / "agent-task-test-worktree"
        assert (resolved.path / "README.md").is_file()

        reused = await resolve_task_workspace(
            config,
            {"mode": "create_worktree", "branch": "agent-task/test-worktree"},
            session_id="session-456",
        )

        assert reused.reused
        assert reused.path == resolved.path

    asyncio.run(scenario())


def test_existing_worktree_requires_configuration_opt_in(tmp_path):
    repo = create_git_repo(tmp_path / "repo")
    config = AppConfig(
        workspace=WorkspaceConfig(allow_existing_worktree=False),
        source_path=repo / "agent-manager.toml",
    )

    async def scenario():
        with pytest.raises(WorkspaceResolutionError) as exc:
            await resolve_task_workspace(
                config,
                {"mode": "existing_worktree", "worktree_path": str(repo)},
                session_id="session-123",
            )

        assert exc.value.code == "existing_worktree_not_allowed"

    asyncio.run(scenario())


def create_git_repo(path: Path) -> Path:
    path.mkdir()
    subprocess.run(["git", "init"], cwd=path, check=True, stdout=subprocess.PIPE)
    subprocess.run(["git", "config", "user.email", "tests@example.invalid"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Tests"], cwd=path, check=True)
    (path / "README.md").write_text("test repo\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=path, check=True, stdout=subprocess.PIPE)
    return path
