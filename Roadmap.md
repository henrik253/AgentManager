# Roadmap

This roadmap tracks the planned work for Agent Manager. Each task is split into subtasks so progress can be updated directly in this file as the repository evolves.

## 1. Project Initialization

Status: Complete

- [x] Define the project goal in `Agent.md`.
- [x] Create a structured roadmap in `Roadmap.md`.
- [x] Choose the initial implementation stack.
  - [x] Python backend service.
  - [x] Python terminal client.
- [x] Add baseline repository files.
  - [x] `.gitignore`
  - [x] Example configuration file
  - [x] Basic development instructions
- [x] Define naming conventions for backends, models, routes, and configuration keys.
- [x] Defer `README.md` creation to the documentation phase.

## 2. Persistent Websocket Service

Status: In progress

- [x] Select the Python websocket server framework.
  - [x] Use the `websockets` asyncio server library.
- [x] Create a minimal service entrypoint.
- [x] Add a persistent websocket session path.
  - [x] Accept a session connection on `/v1/session`.
  - [x] Accept prompt submission messages.
  - [x] Accept optional backend selection.
  - [x] Accept optional model or tier preference.
  - [x] Accept optional task workspace hints.
  - [x] Validate required message fields.
  - [x] Support client-side cancellation messages.
- [x] Define the streaming event format.
  - [x] Session accepted event.
  - [x] Routing decision event.
  - [x] Workspace planning event.
  - [ ] Backend process started event.
  - [ ] Stdout chunk event.
  - [ ] Stderr chunk event.
  - [x] Status update event.
  - [ ] Final success event.
  - [x] Final failure event.
  - [ ] Backend metadata.
  - [ ] Exit status metadata.
- [ ] Add basic connection and session logging.
- [x] Add local-only default binding for safer development.
- [x] Avoid HTTP task submission endpoints.

## 3. Backend Abstraction

Status: In progress

- [x] Define a common backend interface.
  - [x] Backend identifier.
  - [x] Display name.
  - [x] Command path.
  - [ ] Supported options.
  - [x] Health or availability check.
- [ ] Implement Claude CLI backend support.
  - [x] Detect whether Claude CLI is installed.
  - [ ] Build command invocation.
  - [ ] Pass prompt safely.
  - [ ] Capture stdout and stderr.
  - [ ] Detect common limit and failure messages.
- [ ] Implement Codex backend support.
  - [x] Detect whether Codex is installed.
  - [ ] Build command invocation.
  - [ ] Pass prompt safely.
  - [ ] Capture stdout and stderr.
  - [ ] Detect common limit and failure messages.
- [ ] Implement Gemini CLI backend support.
  - [x] Detect whether Gemini CLI is installed.
  - [ ] Build command invocation.
  - [ ] Pass prompt safely.
  - [ ] Capture stdout and stderr.
  - [ ] Detect common limit and failure messages.
- [ ] Add backend execution timeout handling.
- [ ] Add structured backend error types.
- [ ] Scope each backend process to a single session and worktree.

## 4. Routing Rules

Status: In progress

- [x] Define the routing configuration format.
  - [x] Default backend.
  - [x] Preferred backend list.
  - [ ] Preferred model or tier list.
  - [x] Fallback behavior.
  - [ ] Force-routing option.
- [x] Implement explicit user routing.
  - [x] Route to a requested backend.
  - [x] Return a clear error for unknown backends.
  - [x] Return a clear error for unavailable backends unless forced.
- [x] Implement automatic routing.
  - [x] Select the first available preferred backend.
  - [x] Skip temporarily limited backends.
  - [x] Fall back when a backend command is missing.
  - [x] Explain which backend was selected and why.
- [x] Add tests for routing priority and fallback behavior.

## 5. Limit And Availability Tracking

Status: In progress

- [x] Define backend availability states.
  - [x] Available.
  - [x] Missing.
  - [x] Temporarily limited.
  - [x] Failed health check.
  - [x] Disabled by configuration.
- [x] Store temporary limit state.
  - [x] Backend identifier.
  - [x] Model or tier identifier when applicable.
  - [x] Reason.
  - [x] First detected timestamp.
  - [x] Retry-after timestamp when known.
- [x] Parse known limit messages.
  - [x] Claude CLI 5-hour or weekly limit messages.
  - [x] Codex limit messages.
  - [x] Generic rate limit messages.
- [x] Add manual reset or override behavior.
- [x] Add availability inspection websocket message or terminal command.

## 6. Local Terminal Client

Status: In progress

- [x] Document the local terminal client design in `docs/TerminalClientDesign.md`.
- [x] Decide whether the client is a shell script, Node CLI, Python CLI, or compiled binary.
  - [x] Use a Python CLI for now so the existing Python package is immediately executable without adding Go to the toolchain.
- [x] Implement prompt submission from the terminal.
  - [x] Accept prompt as an argument.
  - [x] Accept prompt from stdin.
  - [x] Accept backend override.
  - [x] Accept model or tier override.
  - [x] Accept workspace branch and worktree hints.
- [x] Open a persistent websocket session to the backend.
- [x] Render streamed websocket events as they arrive.
- [x] Print backend selection metadata.
- [x] Print agent output cleanly.
- [x] Return meaningful exit codes.
- [x] Add examples for common workflows.

## 7. Configuration Management

Status: Complete

- [x] Decide configuration file name and format.
  - [x] Use TOML with `agent-manager.toml` and untracked `agent-manager.local.toml`.
- [x] Load project-local configuration.
- [x] Validate configuration schema.
- [x] Provide useful validation errors.
- [x] Define workspace configuration.
  - [x] Allowed worktree root.
  - [x] Task branch prefix.
  - [x] Existing worktree attachment rules.
- [x] Support environment variable overrides for sensitive values.
- [x] Add example configurations.
  - [x] Claude-first routing.
  - [x] Codex-first routing.
  - [x] Explicit-only routing.
  - [x] Fallback-enabled routing.

## 8. Security And Process Safety

Status: Not started

- [ ] Avoid shell interpolation for prompt execution.
- [ ] Use argument arrays instead of command strings where possible.
- [ ] Define which environment variables are passed to backends.
- [ ] Restrict agent execution to the resolved task worktree.
- [ ] Prevent arbitrary filesystem paths from being used as worktrees unless explicitly allowed.
- [ ] Add request size limits.
- [ ] Add execution timeouts.
- [ ] Add optional authentication for non-local access.
- [ ] Document safe deployment assumptions.

## 9. Observability

Status: Not started

- [ ] Add structured logs.
- [ ] Log routing decisions.
- [ ] Log backend execution duration.
- [ ] Log backend failures without leaking prompt content by default.
- [ ] Add a health endpoint for process-level readiness.
- [ ] Add a backend status endpoint or websocket inspection message.

## 10. Testing

Status: Not started

- [ ] Add unit tests for routing logic.
- [ ] Add unit tests for configuration parsing.
- [ ] Add unit tests for limit detection.
- [ ] Add integration tests with mocked backend commands.
- [ ] Add websocket session tests.
- [x] Add terminal client tests.
- [ ] Document how to run the test suite.

## 11. Documentation

Status: Not started

- [ ] Create `README.md`.
  - [ ] Explain the project purpose.
  - [ ] Show installation steps.
  - [ ] Show server startup steps.
  - [ ] Show terminal client usage.
  - [ ] Explain persistent websocket transport.
  - [ ] Show routing examples.
- [ ] Document configuration options.
- [x] Document websocket message and event shape.
- [ ] Document backend setup.
  - [ ] Claude CLI setup assumptions.
  - [ ] Codex setup assumptions.
- [ ] Document troubleshooting.
  - [ ] Missing backend CLI.
  - [ ] Rate limit detected.
  - [ ] Backend command failed.
  - [ ] Websocket connection unavailable.

## 12. Future Enhancements

Status: Not started

- [ ] Job queue for long-running tasks.
- [ ] Persistent task history.
- [ ] Web dashboard for backend status.
- [ ] Additional agent backends.
- [ ] Per-repository routing profiles.
- [ ] Provider API integrations for richer usage-limit detection.
- [ ] Concurrent task controls.
- [ ] Session list and reconnect support.
