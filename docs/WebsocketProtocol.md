# Websocket Protocol

Agent Manager uses a persistent websocket connection for task submission and streaming agent activity. The initial session path is `/v1/session`.

Each websocket session represents one agent task. Multiple websocket sessions may be open at the same time, and each running agent should be scoped to its own task branch and git worktree.

HTTP task submission endpoints are intentionally out of scope. HTTP may be used later for narrow readiness or inspection APIs.

## Client Messages

Client messages are JSON objects with a required `type` string.

### `prompt.submit`

Submits a prompt to be routed to an agent backend.

```json
{
  "type": "prompt.submit",
  "prompt": "Fix the failing tests",
  "backend": "codex",
  "model": "default",
  "workspace": {
    "mode": "create_worktree",
    "branch": "agent-task/fix-tests"
  }
}
```

Fields:

- `prompt`: Required non-empty string.
- `backend`: Optional backend identifier.
- `model`: Optional model or tier identifier.
- `workspace`: Optional object describing where the task should run.

Workspace fields:

- `mode`: Optional string. Initial values are `create_worktree` and `existing_worktree`.
- `branch`: Optional branch name to create or use for the task. When omitted in `create_worktree` mode, the service generates a branch from `workspace.branch_prefix` and the session id.
- `worktree_path`: Optional path for an existing worktree. The service only accepts this in `existing_worktree` mode when `workspace.allow_existing_worktree` is enabled, and validates that the path is a git worktree before using it.

When no workspace is provided, the service creates or reuses a task git worktree under the configured `workspace.worktree_root`. Backend processes run with their current working directory set to the resolved worktree.

### `session.cancel`

Requests cancellation of the active prompt for the websocket session.

```json
{
  "type": "session.cancel"
}
```

### `availability.list`

Requests backend availability and temporary limit state known to the server.

```json
{
  "type": "availability.list",
  "backend": "claude",
  "model": "default"
}
```

Fields:

- `backend`: Optional backend identifier filter.
- `model`: Optional model or tier filter. Model-specific limits are matched before backend-wide limits.

The server responds with an `availability.list` event containing:

- `backend`: The requested backend filter, or `null`.
- `model`: The requested model filter, or `null`.
- `backends`: Backend availability objects.
- `limits`: Temporary limit objects currently stored in memory.

Availability states are stable strings: `available`, `missing`, `temporarily_limited`, `failed_health_check`, and `disabled`.

Temporary limit objects include:

- `backend_id`: Backend identifier.
- `model`: Model or tier identifier, or `null` for backend-wide limits.
- `reason`: Limit reason detected from backend output or recorded by the service.
- `first_detected`: UTC ISO-8601 timestamp.
- `retry_after`: UTC ISO-8601 timestamp when known, otherwise `null`.

### `availability.reset`

Clears temporary limit state. Without filters, all temporary limits are cleared.

```json
{
  "type": "availability.reset",
  "backend": "claude",
  "model": "default"
}
```

Fields:

- `backend`: Optional backend identifier filter.
- `model`: Optional model or tier filter.

The server responds with an `availability.reset` event containing `reset_count` and the remaining backend availability after reset.

## Server Events

Server events are JSON objects with these common fields:

- `type`: Event type.
- `session_id`: Server-generated session identifier.
- `sequence`: Monotonic event number within the session.
- `timestamp`: UTC ISO-8601 timestamp.

Current task lifecycle events:

- `session.accepted`: The websocket session is open.
- `routing.decision`: Routing input and selected backend metadata.
- `workspace.planned`: Task workspace intent, branch, and worktree metadata.
- `workspace.ready`: Resolved workspace metadata after validation or git worktree creation.
- `workspace.failure`: Structured workspace resolution failure.
- `process.started`: Backend process metadata after a subprocess starts.
- `status.update`: Session or backend status changed.
- `stdout.chunk`: A chunk of backend stdout.
- `stderr.chunk`: A chunk of backend stderr.
- `error`: Recoverable or terminal protocol error.
- `availability.list`: Backend availability inspection response.
- `availability.reset`: Manual temporary limit reset response.
- `final.success`: Task completed successfully.
- `final.failure`: Task failed, was cancelled, or could not start.

### Workspace Events

`workspace.planned` preserves the client request and relevant configuration:

```json
{
  "type": "workspace.planned",
  "mode": "create_worktree",
  "requested_branch": "agent-task/fix-tests",
  "requested_worktree_path": null,
  "worktree_root": ".agent-manager/worktrees",
  "branch_prefix": "agent-task/",
  "allow_existing_worktree": false
}
```

`workspace.ready` reports the cwd selected for backend execution:

```json
{
  "type": "workspace.ready",
  "mode": "create_worktree",
  "branch": "agent-task/fix-tests",
  "worktree_path": "/repo/.agent-manager/worktrees/agent-task-fix-tests",
  "reused": false
}
```

If workspace resolution fails, the server emits `workspace.failure` and then `final.failure` with the same failure code and message.

### Process Events

`process.started` is emitted after `asyncio.create_subprocess_exec` successfully starts the configured backend command. The service passes the configured command and args as an argument array; it does not use shell interpolation.

```json
{
  "type": "process.started",
  "backend": "codex",
  "command": "codex",
  "args": ["--some-option"],
  "pid": 12345,
  "cwd": "/repo/.agent-manager/worktrees/agent-task-fix-tests"
}
```

Stdout and stderr are streamed as chunks while the process runs:

```json
{
  "type": "stdout.chunk",
  "backend": "codex",
  "stream": "stdout",
  "chunk": "agent output\n",
  "cwd": "/repo/.agent-manager/worktrees/agent-task-fix-tests"
}
```

`stderr.chunk` uses the same shape with `stream` set to `stderr`.

### Final Events

`final.success` and backend-process `final.failure` include backend, command, exit status, duration, workspace, and temporary-limit metadata:

```json
{
  "type": "final.success",
  "backend": "codex",
  "command": ["codex"],
  "exit_code": 0,
  "duration_seconds": 1.23,
  "workspace": {
    "mode": "create_worktree",
    "branch": "agent-task/fix-tests",
    "worktree_path": "/repo/.agent-manager/worktrees/agent-task-fix-tests",
    "reused": false
  },
  "temporary_limit": null
}
```

A non-zero backend exit returns `final.failure` with `code` set to `backend_process_failed`. If stdout or stderr contains a known rate-limit or quota message, `temporary_limit` contains the stored availability limit and the backend is temporarily skipped by later automatic routing decisions until the limit expires or is reset.
