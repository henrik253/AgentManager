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
- `branch`: Optional branch name to create or use for the task.
- `worktree_path`: Optional path for an existing worktree. The service must validate this path against workspace configuration before using it.

When no workspace is provided, the service should create or allocate a task worktree using project configuration. It should not run multiple active agent sessions in the same mutable checkout by default.

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

Initial phase 2 events:

- `session.accepted`: The websocket session is open.
- `routing.decision`: Routing input and selected backend metadata.
- `workspace.planned`: Task workspace intent, branch, and worktree metadata.
- `status.update`: Session or backend status changed.
- `stdout.chunk`: A chunk of backend stdout.
- `stderr.chunk`: A chunk of backend stderr.
- `error`: Recoverable or terminal protocol error.
- `availability.list`: Backend availability inspection response.
- `availability.reset`: Manual temporary limit reset response.
- `final.success`: Task completed successfully.
- `final.failure`: Task failed, was cancelled, or could not start.

Backend execution and worktree creation are implemented in later phases. Until then, `prompt.submit` validates the persistent websocket flow, emits `workspace.planned`, and returns `final.failure` with `code` set to `backend_execution_not_implemented`.
