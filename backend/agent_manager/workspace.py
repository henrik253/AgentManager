from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from pathlib import Path

from agent_manager.config import AppConfig


class WorkspaceResolutionError(RuntimeError):
    def __init__(self, code: str, message: str, *, detail: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.detail = detail


@dataclass(frozen=True)
class ResolvedWorkspace:
    mode: str
    branch: str | None
    path: Path
    reused: bool = False

    def to_event_payload(self) -> dict:
        return {
            "mode": self.mode,
            "branch": self.branch,
            "worktree_path": str(self.path),
            "reused": self.reused,
        }


async def resolve_task_workspace(
    config: AppConfig,
    workspace: dict,
    *,
    session_id: str,
) -> ResolvedWorkspace:
    project_root = await find_project_root(config)
    mode = workspace.get("mode", "create_worktree")
    if mode == "existing_worktree":
        return await resolve_existing_worktree(config, project_root, workspace)
    return await create_or_reuse_worktree(config, project_root, workspace, session_id=session_id)


async def find_project_root(config: AppConfig) -> Path:
    start = config.source_path.parent if config.source_path is not None else Path.cwd()
    result = await run_git(start, "rev-parse", "--show-toplevel")
    if result.returncode != 0:
        raise WorkspaceResolutionError(
            "git_repository_not_found",
            "could not find a git repository for workspace creation",
            detail=result.stderr.strip() or result.stdout.strip() or None,
        )
    return Path(result.stdout.strip()).resolve()


async def resolve_existing_worktree(
    config: AppConfig,
    project_root: Path,
    workspace: dict,
) -> ResolvedWorkspace:
    if not config.workspace.allow_existing_worktree:
        raise WorkspaceResolutionError(
            "existing_worktree_not_allowed",
            "existing worktree mode is disabled by configuration",
        )

    requested_path = workspace.get("worktree_path")
    if not requested_path:
        raise WorkspaceResolutionError(
            "existing_worktree_path_required",
            "workspace.worktree_path is required for existing_worktree mode",
        )

    path = Path(requested_path)
    if not path.is_absolute():
        path = project_root / path
    path = path.resolve()
    if not path.is_dir():
        raise WorkspaceResolutionError(
            "existing_worktree_not_found",
            f"existing worktree path does not exist: {path}",
        )

    result = await run_git(path, "rev-parse", "--is-inside-work-tree")
    if result.returncode != 0 or result.stdout.strip() != "true":
        raise WorkspaceResolutionError(
            "existing_worktree_invalid",
            f"existing worktree path is not a git worktree: {path}",
            detail=result.stderr.strip() or None,
        )

    branch = workspace.get("branch") or await current_branch(path)
    return ResolvedWorkspace(mode="existing_worktree", branch=branch, path=path, reused=True)


async def create_or_reuse_worktree(
    config: AppConfig,
    project_root: Path,
    workspace: dict,
    *,
    session_id: str,
) -> ResolvedWorkspace:
    branch = workspace.get("branch") or generated_branch(config, session_id)
    await validate_branch_name(project_root, branch)

    worktree_root = (project_root / config.workspace.worktree_root).resolve()
    if project_root not in (worktree_root, *worktree_root.parents):
        raise WorkspaceResolutionError(
            "invalid_worktree_root",
            "configured worktree root must resolve inside the project repository",
        )
    worktree_root.mkdir(parents=True, exist_ok=True)
    worktree_path = worktree_root / branch_slug(branch)

    if worktree_path.exists():
        if not worktree_path.is_dir():
            raise WorkspaceResolutionError(
                "worktree_path_conflict",
                f"worktree path exists and is not a directory: {worktree_path}",
            )
        result = await run_git(worktree_path, "rev-parse", "--is-inside-work-tree")
        if result.returncode == 0 and result.stdout.strip() == "true":
            return ResolvedWorkspace(
                mode="create_worktree",
                branch=branch,
                path=worktree_path.resolve(),
                reused=True,
            )
        raise WorkspaceResolutionError(
            "worktree_path_conflict",
            f"worktree path exists but is not a git worktree: {worktree_path}",
        )

    result = await run_git(
        project_root,
        "worktree",
        "add",
        "-b",
        branch,
        str(worktree_path),
        "HEAD",
    )
    if result.returncode != 0:
        existing_branch = await run_git(
            project_root,
            "worktree",
            "add",
            str(worktree_path),
            branch,
        )
        if existing_branch.returncode != 0:
            raise WorkspaceResolutionError(
                "worktree_creation_failed",
                f"git worktree creation failed for branch {branch}",
                detail=existing_branch.stderr.strip() or result.stderr.strip() or None,
            )

    return ResolvedWorkspace(
        mode="create_worktree",
        branch=branch,
        path=worktree_path.resolve(),
        reused=False,
    )


async def validate_branch_name(project_root: Path, branch: str) -> None:
    if not branch or branch.startswith("-") or any(char.isspace() for char in branch):
        raise WorkspaceResolutionError(
            "invalid_branch_name",
            "workspace branch must be non-empty and must not contain whitespace",
        )
    result = await run_git(project_root, "check-ref-format", "--branch", branch)
    if result.returncode != 0:
        raise WorkspaceResolutionError(
            "invalid_branch_name",
            f"workspace branch is not a valid git branch name: {branch}",
            detail=result.stderr.strip() or None,
        )


def generated_branch(config: AppConfig, session_id: str) -> str:
    suffix = session_id.replace("-", "")[:12]
    return f"{config.workspace.branch_prefix}{suffix}"


def branch_slug(branch: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", branch).strip(".-")
    return slug or "task"


async def current_branch(path: Path) -> str | None:
    result = await run_git(path, "branch", "--show-current")
    branch = result.stdout.strip()
    return branch or None


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


async def run_git(cwd: Path, *args: str) -> CommandResult:
    process = await asyncio.create_subprocess_exec(
        "git",
        *args,
        cwd=str(cwd),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    return CommandResult(
        returncode=process.returncode or 0,
        stdout=stdout.decode("utf-8", errors="replace"),
        stderr=stderr.decode("utf-8", errors="replace"),
    )
