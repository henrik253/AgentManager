# Development

Agent Manager uses a Python backend service and a local terminal client. The terminal client contract is language-neutral; the first executable client may be Python because it matches the backend toolchain and avoids requiring Go in environments where Go is not installed.

## Repository Layout

Planned layout:

- `backend/`: Python websocket service, routing logic, backend execution, and configuration loading.
- `backend/agent_manager/client.py` or `cmd/agent-manager/`: terminal client entrypoint, depending on the implementation language chosen for the current phase.
- `config/`: Example configuration files.
- `docs/`: Project documentation that is not part of the README.
- `tests/`: Backend tests and integration fixtures when the backend is added.

Runtime agent tasks should use separate git worktrees. The service architecture should allow multiple websocket sessions to run concurrently, with each session owning one backend process and one task workspace.

Initial backend detection checks for the configured command on `PATH`. The default backend commands are `claude`, `codex`, and `gemini`.

## Development Workflow

By default, new tasks should be implemented in a separate git worktree on a task branch. The user may explicitly allow work on `main` for small repository setup changes.

Before committing code changes, run the relevant checks for the files touched. Documentation-only changes should at least be reviewed with `git diff --check`.

## Naming Conventions

These conventions are part of the project contract and should stay stable unless intentionally migrated.

- Backend identifiers use lowercase kebab-case or single lowercase words, such as `claude`, `codex`, or `local-agent`.
- Python package and module names use lowercase snake_case.
- Go packages, if a compiled client is added later, use short lowercase names without underscores.
- CLI commands and flags use kebab-case.
- Websocket paths use versioned kebab-case resources, such as `/v1/session`.
- HTTP routes are reserved for optional non-task APIs such as health and backend status.
- JSON and TOML keys use snake_case.
- Environment variables use the `AGENT_MANAGER_` prefix and uppercase snake_case.
- Git branches use kebab-case with a short type prefix, such as `docs/initialize-project` or `feature/routing-rules`.
