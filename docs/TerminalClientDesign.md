# Local Terminal Client Design

This document defines the initial local terminal client contract for Agent Manager. It is intentionally implementation-oriented so phase 6 can proceed without changing the websocket service design.

The client may start as a Python CLI because the backend is already Python and Go is not available in the current environment. That choice keeps the first executable client easy to test and ship from this repository. The command and protocol contract should stay language-neutral so a future compiled client can replace or wrap the Python entrypoint without changing user workflows.

## Goals

- Submit one prompt to one persistent websocket session.
- Preserve the service model where each websocket session represents one agent task.
- Render routing metadata, workspace metadata, backend availability, status, stdout, stderr, final results, and errors as events arrive.
- Support automatic routing and explicit backend/model overrides.
- Support task workspace hints without creating or validating worktrees in the client.
- Make stdin, cancellation, reconnect behavior, and exit codes predictable for scripts.
- Keep the first client project-local and dependency-light.

## Non-Goals

- Do not create task worktrees in the client. The service owns workspace allocation, validation, and backend execution directory selection.
- Do not run Claude, Codex, Gemini, or other agent commands directly from the client.
- Do not multiplex multiple prompts over one websocket session in the initial client.
- Do not implement a durable job queue, session history database, or background daemon in the initial client.
- Do not add HTTP task submission. Agent interaction remains websocket-based.
- Do not require a compiled binary for phase 6. A compiled client can be added later if packaging or startup latency justifies it.

## Command Shape

The initial executable should expose a single task submission command. If the implementation uses Python, `python -m agent_manager.client` is acceptable for development, with a console script such as `agent-manager` added when packaging is ready.

Recommended shape:

```text
agent-manager run [PROMPT] [flags]
```

Useful aliases can be added later, but the documented command should remain stable.

Recommended flags:

- `--server-url URL`: Full websocket URL. Defaults to `ws://127.0.0.1:8765/v1/session` unless config or environment overrides it.
- `--host HOST`, `--port PORT`, `--path PATH`: Optional pieces for building the websocket URL when `--server-url` is not supplied.
- `--backend ID`: Explicit backend request, passed as `backend` in `prompt.submit`.
- `--model ID`: Optional model or tier request, passed as `model`.
- `--workspace-mode MODE`: `create_worktree` or `existing_worktree`.
- `--branch NAME`: Requested task branch name.
- `--worktree-path PATH`: Existing worktree path hint. The service must still validate this against configuration.
- `--prompt-file PATH`: Read the prompt from a file.
- `--stdin`: Force prompt read from stdin.
- `--json`: Emit newline-delimited raw event JSON for automation.
- `--no-color`: Disable color in human rendering.
- `--quiet`: Suppress routing/workspace/status summaries; still print backend stdout and stderr.
- `--verbose`: Include event sequence ids, timestamps, and detailed metadata.
- `--connect-timeout SECONDS`: Time limit for opening the websocket.
- `--idle-timeout SECONDS`: Optional no-event timeout. Default should be no idle timeout for long-running agents.

Validation rules:

- `--server-url` conflicts with `--host`, `--port`, and `--path`.
- `--prompt-file` conflicts with positional `PROMPT` and `--stdin`.
- `--workspace-mode existing_worktree` should require `--worktree-path`.
- `--worktree-path` without `--workspace-mode` should imply `existing_worktree`.
- `--branch` without `--workspace-mode` should imply `create_worktree`.

## Prompt Sources And Stdin

Prompt source priority should be explicit and script-friendly:

1. Positional `PROMPT`.
2. `--prompt-file PATH`.
3. `--stdin`.
4. Implicit stdin only when stdin is not a TTY.

The client should reject ambiguous combinations rather than concatenate inputs. It should trim only trailing line endings added by shell usage; it should not strip meaningful leading whitespace or internal formatting. Empty or whitespace-only prompts should fail locally before opening a websocket.

Interactive stdin should be reserved for cancellation and future interaction. The initial client should not open an editor or prompt the user for missing text.

## Websocket Lifecycle

The client opens one websocket connection to the configured session path and waits for `session.accepted` before sending `prompt.submit`.

Submission payload:

```json
{
  "type": "prompt.submit",
  "prompt": "Fix the failing tests",
  "backend": "codex",
  "model": "default",
  "workspace": {
    "mode": "create_worktree",
    "branch": "agent-task/fix-tests",
    "worktree_path": null
  }
}
```

Fields with no user input may be omitted where the protocol allows it. The client should not invent defaults for routing or workspace behavior beyond explicit CLI flags; server configuration owns those defaults.

Lifecycle expectations:

- The connection is persistent for the duration of the task.
- The client should process events in received order and treat `sequence` as diagnostic metadata, not as an instruction to reorder messages.
- `final.success` and `final.failure` are terminal events. After rendering the final event, the client should close the websocket cleanly and exit with the mapped exit code.
- A protocol `error` event with `recoverable=true` should be rendered and the client should continue unless a final event follows.
- A protocol `error` event with `recoverable=false` should be treated as terminal if no final event follows.
- If the websocket closes before a final event, the client should report an interrupted session and return the transport exit code.

Reconnect policy:

- Do not silently reconnect an active task in phase 6. The current protocol has no resume token or replay contract, so reconnecting could duplicate prompts.
- A failed connection before `prompt.submit` may be retried only when the user opts in through a future retry flag.
- Future reconnect support should require server-side session identifiers, resume semantics, and idempotent submission handling.

Cancellation:

- On `Ctrl-C` while connected, send `{"type":"session.cancel"}` once, then wait briefly for `final.failure` with `code=cancelled`.
- A second `Ctrl-C` should close the websocket immediately and return the interrupted exit code.
- If cancellation cannot be sent because the connection is already closed, report that state and return the transport exit code unless a final event was already received.

## Event Rendering

The default renderer is human-oriented and streaming. `--json` switches to newline-delimited raw event JSON with no additional text.

Common rendering rules:

- Preserve backend stdout and stderr chunk content exactly.
- Send `stdout.chunk` payload text to client stdout.
- Send `stderr.chunk`, status metadata, routing metadata, workspace metadata, errors, and summaries to client stderr.
- In non-TTY output, disable color and other terminal control sequences.
- In verbose mode, prefix metadata lines with timestamp, session id, and sequence.

Event-specific strategy:

- `session.accepted`: In verbose mode, print the session id and websocket path. In default mode, stay quiet.
- `routing.decision`: Print the selected backend, requested backend when provided, requested model when provided, and the routing reason. Include `selected_backend_metadata.state` and `reason` so availability and limit decisions are visible.
- `availability.snapshot` or future inspection events: Render a compact table with backend id, display name, state, enabled flag, retry-after when present, and reason. Until a dedicated event exists, use `available_backends` from `routing.decision`.
- `workspace.planned`: Print mode, requested branch, requested worktree path, worktree root, branch prefix, and whether existing worktrees are allowed. The resolved branch/worktree fields should be rendered when later phases add them.
- `workspace.ready` or future workspace events: Print the resolved branch and worktree path.
- `status.update`: Print concise status transitions. Known statuses such as `waiting_for_backend_execution`, `starting`, `running`, `cancelled`, and `completed` should have stable wording.
- `process.started` or future backend-start event: Print backend id, command display name, pid when safe, and worktree path.
- `stdout.chunk`: Stream chunk text to stdout without adding prefixes or extra newlines.
- `stderr.chunk`: Stream chunk text to stderr without adding prefixes or extra newlines.
- `error`: Print `code` and `message`. Include whether it is recoverable in verbose mode.
- `final.success`: Print a short completion summary to stderr unless `--quiet` is set. Use event `exit_code` if present.
- `final.failure`: Print failure `code`, message or detail when present, and backend exit code when present.

The renderer should tolerate unknown event types by printing a verbose metadata line and continuing. In `--json` mode, unknown events pass through unchanged.

## Exit Code Contract

The client exit code is part of the scripting interface and should remain stable:

- `0`: Final success.
- `1`: Final failure from the service when no more specific code applies.
- `2`: Local usage error, invalid flags, missing prompt, or invalid prompt source.
- `3`: Configuration error, including invalid server URL or unreadable prompt file.
- `4`: Transport error, including connection failure, websocket close before a final event, or timeout.
- `5`: Protocol error, including invalid JSON event shape or terminal non-recoverable protocol error without a final event.
- `130`: Interrupted locally by a second `Ctrl-C` or by `SIGINT` before cancellation completes.

When a final event includes a backend `exit_code`, the client should not blindly return that value if it conflicts with this contract. It may display the backend exit code and return `1` for `final.failure`, unless a later design explicitly reserves a passthrough mode.

## Configuration And Environment

Configuration should be optional for the first client. Flags have highest priority, followed by environment variables, followed by project config, followed by built-in defaults.

Recommended environment variables:

- `AGENT_MANAGER_SERVER_URL`: Full websocket URL.
- `AGENT_MANAGER_HOST`: Server host when URL is not set.
- `AGENT_MANAGER_PORT`: Server port when URL is not set.
- `AGENT_MANAGER_WEBSOCKET_PATH`: Websocket path when URL is not set.
- `AGENT_MANAGER_BACKEND`: Default backend request.
- `AGENT_MANAGER_MODEL`: Default model or tier request.
- `AGENT_MANAGER_NO_COLOR`: Disable color when set to a truthy value.
- `AGENT_MANAGER_JSON`: Emit raw JSON events when set to a truthy value.
- `AGENT_MANAGER_CONNECT_TIMEOUT`: Default connect timeout in seconds.

The client should not read provider API keys or agent-specific credentials. Backend process environment is owned by the service.

## Concurrent Sessions And Worktrees

Concurrency is achieved by running multiple client processes. Each process opens one websocket session and submits one task. The client should not coordinate locks, branch names, or worktree paths across processes.

Responsibilities:

- The client passes workspace hints from flags.
- The service validates existing worktree paths.
- The service creates or allocates task worktrees under configured roots.
- The service prevents active sessions from sharing the same mutable checkout unless configuration explicitly allows it.
- The service returns routing and workspace events that let each terminal display where its task is running.

For human readability, the client should include the server `session_id` in verbose output and in error summaries. This helps users distinguish concurrent terminal windows without requiring a local session registry.

## Testing Strategy

Unit tests:

- Argument parsing and flag conflict validation.
- Prompt source priority and stdin behavior.
- Environment/config precedence.
- `prompt.submit` JSON construction.
- Exit code mapping.
- Event rendering for known and unknown events.

Integration tests:

- Client connects to a mocked websocket server and waits for `session.accepted`.
- Client sends the expected `prompt.submit` payload.
- Client streams `stdout.chunk` and `stderr.chunk` to the correct streams.
- Client renders `routing.decision`, `workspace.planned`, `status.update`, `error`, and final events.
- Client handles server close before final as a transport failure.
- Client sends `session.cancel` on interrupt where the test harness can simulate it.

End-to-end smoke tests:

- Run the Python service locally.
- Submit a prompt with automatic routing.
- Submit a prompt with `--backend`.
- Submit a prompt from stdin.
- Submit a prompt with workspace branch hints.
- Confirm current phase behavior returns `backend_execution_not_implemented` until backend execution lands.

## Near-Term Handoff Checklist

- Add the initial client entrypoint in the phase 6 implementation branch, preferably Python for immediate executability in this environment.
- Keep command names and flags aligned with this design or update this document before diverging.
- Use the existing `/v1/session` websocket path and wait for `session.accepted` before sending `prompt.submit`.
- Reuse the documented event names from `docs/WebsocketProtocol.md`.
- Render `routing.decision.available_backends` so phase 5 availability states and limit reasons are visible without a separate command.
- Keep workspace behavior client-light: pass hints, render server decisions, do not create worktrees locally.
- Implement stable exit code mapping before adding formatting polish.
- Add tests with a mocked websocket server before relying on a live backend process.
- Leave a clear path for a future compiled client by keeping protocol, flags, and rendering behavior independent of Python internals.
