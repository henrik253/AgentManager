# Agent Manager

Agent Manager is a project-local service for routing prompts from a local terminal to agent CLIs installed on this server. The first supported agent backends are Claude CLI, Codex, and Gemini CLI.

The core goal is to provide a persistent websocket connection that can start an available agent with a supplied prompt, then stream the agent's activity, output, status changes, and final result back to the caller as they happen.

## Problem

Developers often work across multiple AI coding agents, each with different strengths, availability limits, and rate windows. This project should make it possible to submit a task once and route it to the best available backend without manually switching commands or tracking every model limit by hand.

## Primary Use Case

A user on a local machine opens a websocket session to this service from a terminal client. The client sends a prompt over that session, the service decides which configured agent backend should handle it, prepares or attaches to a task-specific git worktree, starts that backend on the server, and streams progress and output back until the agent completes.

Example workflow:

1. User runs a terminal command with a prompt.
2. The command opens or reuses a websocket connection to Agent Manager.
3. Agent Manager selects an agent backend.
4. Agent Manager creates or selects a separate branch/worktree for the task.
5. Agent Manager starts Claude CLI, Codex, or Gemini CLI with the prompt inside that worktree.
6. Agent Manager streams routing information, workspace metadata, process lifecycle events, stdout, stderr, and the final result back to the user.

Multiple sessions should be able to run at the same time. For example, a user can keep Task A running in one websocket session and start Task B in another session, with each agent operating in its own branch checkout and worktree.

## Routing Goals

Routing should support both explicit user choice and automatic rules.

Explicit routing:

- User chooses the target backend directly.
- User can request a specific model or model tier when the backend supports it.
- The service validates that the requested backend is configured and available.

Ruleset routing:

- User can define a preferred ordered list of backends or models.
- The service chooses the highest-priority available option.
- If the preferred option is unavailable because of a rate limit, usage window, missing CLI, or backend health issue, the service falls back to the next option.
- Rules should be project-local so each repository can have its own routing preferences.

## Availability And Limits

The service should track or infer backend availability wherever possible.

Initial limit handling may be simple:

- Detect known CLI errors that indicate daily, 5-hour, weekly, or account limits.
- Mark a backend or model as temporarily unavailable when a limit is detected.
- Store enough state to avoid immediately retrying a known-limited backend.
- Allow manual override when the user still wants to force a backend.

More advanced limit handling can be added later:

- Backend health checks.
- Configurable cooldown windows.
- Per-model usage state.
- Better parsing of provider-specific limit messages.

## Configuration

Configuration should live in the project using this application. It should define:

- Available agent backends.
- Backend command paths and invocation options.
- Where task worktrees may be created.
- Branch naming rules for agent tasks.
- Preferred routing order.
- Per-project defaults.
- Optional fallback behavior.
- Security and execution constraints.

Configuration should be human-readable and easy to version with the project.

The initial configuration format is TOML. Shared examples live under `config/`, while machine-specific overrides should use `agent-manager.local.toml` and stay out of git.

## Implementation Stack

The backend service is written in Python. It owns the websocket server, configuration loading, routing rules, backend availability state, and process execution for agent CLIs.

The local terminal client owns argument parsing, stdin handling, websocket session management, streaming output formatting, and meaningful terminal exit codes. The client contract is language-neutral: the first executable client may be Python for pragmatic local development, while a future compiled client remains possible.

## Naming Conventions

Project naming should be predictable across configuration, routes, code, and logs.

- Backend identifiers use lowercase kebab-case or single lowercase words, such as `claude`, `codex`, or `local-agent`.
- Python package and module names use lowercase snake_case.
- Go packages, if a compiled client is added later, use short lowercase names without underscores.
- CLI commands and flags use kebab-case.
- Websocket paths use versioned kebab-case resources, such as `/v1/session`.
- HTTP routes are reserved for optional non-task APIs such as health and backend status.
- JSON and TOML keys use snake_case.
- Environment variables use the `AGENT_MANAGER_` prefix and uppercase snake_case.
- Git branches use kebab-case with a short type prefix, such as `docs/initialize-project` or `feature/routing-rules`.

## Websocket Session Responsibilities

The websocket session should:

- Accept a prompt or task payload as a client message.
- Accept optional routing preferences.
- Accept optional workspace preferences, such as a requested branch name or existing worktree path.
- Validate the request.
- Resolve the target backend.
- Resolve the task workspace without sharing mutable checkout state with other active sessions.
- Start the selected agent process.
- Stream structured events for routing decisions, workspace preparation, process start, stdout chunks, stderr chunks, status updates, errors, cancellation, exit code, and relevant metadata.
- Return a clear final success or failure event.
- Keep the client experience close to the native agent by preserving backend-specific output where possible.
- Avoid leaking secrets or unrelated environment details.

The initial service should avoid HTTP task submission endpoints. HTTP can be added later for narrow inspection APIs, but agent interaction should use the persistent websocket transport.

Each websocket session represents one interactive agent task. The service may support multiple simultaneous sessions, but each running backend process must be scoped to one session and one task workspace. Shared project state should be limited to configuration, routing state, and backend availability state.

## Non-Goals For The Initial Version

- Hosting a general multi-user SaaS product.
- Replacing Claude CLI or Codex.
- Building a full workflow orchestration platform.
- Implementing provider billing or usage APIs before basic local routing works.
- Supporting every possible agent backend before the core abstraction is stable.

## Design Principles

- Keep the first version small and operational.
- Prefer explicit configuration over hidden behavior.
- Make routing decisions explainable.
- Preserve backend-specific output instead of over-normalizing too early.
- Treat command execution and prompt handling as security-sensitive.
- Make the tool useful from a terminal before adding richer interfaces.

## Development Workflow

Every task or feature should be implemented in a separate git worktree on a new branch. Work should not be done directly on the main project checkout unless the user explicitly requests it.

Expected workflow:

1. Create a new branch for the task or feature.
2. Create a separate worktree for that branch.
3. Implement the requested change inside that worktree.
4. Run the relevant checks or tests.
5. Commit the completed work on the task branch.
6. Report the branch name, worktree path, commit hash, and verification result.

Each completed task should end with a commit that contains only the relevant changes for that task.
