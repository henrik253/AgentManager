# Development

Agent Manager uses a Python backend service and a Go terminal client.

## Repository Layout

Planned layout:

- `backend/`: Python websocket service, routing logic, backend execution, and configuration loading.
- `cmd/agent-manager/`: Go terminal client entrypoint.
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
- Go packages use short lowercase names without underscores.
- CLI commands and flags use kebab-case.
- Websocket paths use versioned kebab-case resources, such as `/v1/session`.
- HTTP routes are reserved for optional non-task APIs such as health and backend status.
- JSON and TOML keys use snake_case.
- Environment variables use the `AGENT_MANAGER_` prefix and uppercase snake_case.
- Git branches use kebab-case with a short type prefix, such as `docs/initialize-project` or `feature/routing-rules`.
