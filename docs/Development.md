# Development

Agent Manager uses a Python backend service and a Python terminal client.

The terminal client was originally planned as Go, but phase 6 uses Python for now
because Go is not required anywhere else in the repository and the Python package
can expose an immediately executable console script.

## Repository Layout

Planned layout:

- `backend/`: Python websocket service, routing logic, backend execution, and configuration loading.
- `backend/agent_manager/client.py`: Python terminal client entrypoint.
- `config/`: Example configuration files.
- `docs/`: Project documentation that is not part of the README.
- `tests/`: Backend tests and integration fixtures when the backend is added.

Runtime agent tasks should use separate git worktrees. The service architecture should allow multiple websocket sessions to run concurrently, with each session owning one backend process and one task workspace.

Initial backend detection checks for the configured command on `PATH`. The default backend commands are `claude`, `codex`, and `gemini`.

## Local Terminal Client

Start the websocket service in one shell:

```sh
agent-manager-server
```

Submit a prompt in another shell:

```sh
agent-manager --backend codex --branch agent-task/fix-tests Fix the failing tests
```

When no prompt arguments are provided, the client reads the prompt from stdin:

```sh
printf 'Summarize the current branch\n' | agent-manager --model default
```

Useful client flags:

- `--url ws://127.0.0.1:8765`: websocket server base URL.
- `--path /v1/session`: websocket session path.
- `--backend codex`: backend routing override.
- `--model default`: model or tier routing hint.
- `--workspace-mode create_worktree`: task workspace mode hint.
- `--branch agent-task/name`: task branch hint.
- `--worktree-path ../AgentManager-task`: existing worktree hint.
- `--json`: render newline-delimited JSON events instead of human output.
- `--timeout 60`: fail if no final event arrives within the timeout.

In human output mode, backend stdout chunks are written to stdout. Routing,
workspace, status, error, and final metadata are written to stderr so command
output remains pipe-friendly.

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
