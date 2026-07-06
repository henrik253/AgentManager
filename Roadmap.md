# Roadmap

This roadmap tracks the planned work for Agent Manager. Each task is split into subtasks so progress can be updated directly in this file as the repository evolves.

## 1. Project Initialization

Status: In progress

- [x] Define the project goal in `Agent.md`.
- [x] Create a structured roadmap in `Roadmap.md`.
- [ ] Choose the initial implementation stack.
- [ ] Add baseline repository files.
  - [ ] `README.md`
  - [ ] `.gitignore`
  - [ ] Example configuration file
  - [ ] Basic development instructions
- [ ] Define naming conventions for backends, models, routes, and configuration keys.

## 2. Core Service Endpoint

Status: Not started

- [ ] Select the HTTP server framework.
- [ ] Create a minimal service entrypoint.
- [ ] Add a prompt submission endpoint.
  - [ ] Accept prompt text.
  - [ ] Accept optional backend selection.
  - [ ] Accept optional model or tier preference.
  - [ ] Validate required fields.
- [ ] Define the response format.
  - [ ] Success payload.
  - [ ] Failure payload.
  - [ ] Backend metadata.
  - [ ] Exit status metadata.
- [ ] Add basic request logging.
- [ ] Add local-only default binding for safer development.

## 3. Backend Abstraction

Status: Not started

- [ ] Define a common backend interface.
  - [ ] Backend identifier.
  - [ ] Display name.
  - [ ] Command path.
  - [ ] Supported options.
  - [ ] Health or availability check.
- [ ] Implement Claude CLI backend support.
  - [ ] Detect whether Claude CLI is installed.
  - [ ] Build command invocation.
  - [ ] Pass prompt safely.
  - [ ] Capture stdout and stderr.
  - [ ] Detect common limit and failure messages.
- [ ] Implement Codex backend support.
  - [ ] Detect whether Codex is installed.
  - [ ] Build command invocation.
  - [ ] Pass prompt safely.
  - [ ] Capture stdout and stderr.
  - [ ] Detect common limit and failure messages.
- [ ] Add backend execution timeout handling.
- [ ] Add structured backend error types.

## 4. Routing Rules

Status: Not started

- [ ] Define the routing configuration format.
  - [ ] Default backend.
  - [ ] Preferred backend list.
  - [ ] Preferred model or tier list.
  - [ ] Fallback behavior.
  - [ ] Force-routing option.
- [ ] Implement explicit user routing.
  - [ ] Route to a requested backend.
  - [ ] Return a clear error for unknown backends.
  - [ ] Return a clear error for unavailable backends unless forced.
- [ ] Implement automatic routing.
  - [ ] Select the first available preferred backend.
  - [ ] Skip temporarily limited backends.
  - [ ] Fall back when a backend command is missing.
  - [ ] Explain which backend was selected and why.
- [ ] Add tests for routing priority and fallback behavior.

## 5. Limit And Availability Tracking

Status: Not started

- [ ] Define backend availability states.
  - [ ] Available.
  - [ ] Missing.
  - [ ] Temporarily limited.
  - [ ] Failed health check.
  - [ ] Disabled by configuration.
- [ ] Store temporary limit state.
  - [ ] Backend identifier.
  - [ ] Model or tier identifier when applicable.
  - [ ] Reason.
  - [ ] First detected timestamp.
  - [ ] Retry-after timestamp when known.
- [ ] Parse known limit messages.
  - [ ] Claude CLI 5-hour or weekly limit messages.
  - [ ] Codex limit messages.
  - [ ] Generic rate limit messages.
- [ ] Add manual reset or override behavior.
- [ ] Add availability inspection endpoint or command.

## 6. Local Terminal Client

Status: Not started

- [ ] Decide whether the client is a shell script, Node CLI, Python CLI, or compiled binary.
- [ ] Implement prompt submission from the terminal.
  - [ ] Accept prompt as an argument.
  - [ ] Accept prompt from stdin.
  - [ ] Accept backend override.
  - [ ] Accept model or tier override.
- [ ] Print backend selection metadata.
- [ ] Print agent output cleanly.
- [ ] Return meaningful exit codes.
- [ ] Add examples for common workflows.

## 7. Configuration Management

Status: Not started

- [ ] Decide configuration file name and format.
- [ ] Load project-local configuration.
- [ ] Validate configuration schema.
- [ ] Provide useful validation errors.
- [ ] Support environment variable overrides for sensitive values.
- [ ] Add example configurations.
  - [ ] Claude-first routing.
  - [ ] Codex-first routing.
  - [ ] Explicit-only routing.
  - [ ] Fallback-enabled routing.

## 8. Security And Process Safety

Status: Not started

- [ ] Avoid shell interpolation for prompt execution.
- [ ] Use argument arrays instead of command strings where possible.
- [ ] Define which environment variables are passed to backends.
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
- [ ] Add a health endpoint.
- [ ] Add a backend status endpoint.

## 10. Testing

Status: Not started

- [ ] Add unit tests for routing logic.
- [ ] Add unit tests for configuration parsing.
- [ ] Add unit tests for limit detection.
- [ ] Add integration tests with mocked backend commands.
- [ ] Add endpoint tests.
- [ ] Add terminal client tests.
- [ ] Document how to run the test suite.

## 11. Documentation

Status: Not started

- [ ] Create `README.md`.
  - [ ] Explain the project purpose.
  - [ ] Show installation steps.
  - [ ] Show server startup steps.
  - [ ] Show terminal client usage.
  - [ ] Show routing examples.
- [ ] Document configuration options.
- [ ] Document backend setup.
  - [ ] Claude CLI setup assumptions.
  - [ ] Codex setup assumptions.
- [ ] Document troubleshooting.
  - [ ] Missing backend CLI.
  - [ ] Rate limit detected.
  - [ ] Backend command failed.
  - [ ] Endpoint unavailable.

## 12. Future Enhancements

Status: Not started

- [ ] Streaming responses from running agents.
- [ ] Job queue for long-running tasks.
- [ ] Persistent task history.
- [ ] Web dashboard for backend status.
- [ ] Additional agent backends.
- [ ] Per-repository routing profiles.
- [ ] Provider API integrations for richer usage-limit detection.
- [ ] Concurrent task controls.
