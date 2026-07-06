# Websocket Protocol

Agent Manager uses a persistent websocket connection for task submission and streaming agent activity. The initial session path is `/v1/session`.

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
  "model": "default"
}
```

Fields:

- `prompt`: Required non-empty string.
- `backend`: Optional backend identifier.
- `model`: Optional model or tier identifier.

### `session.cancel`

Requests cancellation of the active prompt for the websocket session.

```json
{
  "type": "session.cancel"
}
```

## Server Events

Server events are JSON objects with these common fields:

- `type`: Event type.
- `session_id`: Server-generated session identifier.
- `sequence`: Monotonic event number within the session.
- `timestamp`: UTC ISO-8601 timestamp.

Initial phase 2 events:

- `session.accepted`: The websocket session is open.
- `routing.decision`: Routing input and selected backend metadata.
- `status.update`: Session or backend status changed.
- `stdout.chunk`: A chunk of backend stdout.
- `stderr.chunk`: A chunk of backend stderr.
- `error`: Recoverable or terminal protocol error.
- `final.success`: Task completed successfully.
- `final.failure`: Task failed, was cancelled, or could not start.

Backend execution is implemented in a later phase. Until then, `prompt.submit` validates the persistent websocket flow and returns `final.failure` with `code` set to `backend_execution_not_implemented`.
