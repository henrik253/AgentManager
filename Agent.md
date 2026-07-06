# Agent Manager

Agent Manager is a project-local service for routing prompts from a local terminal to agent CLIs installed on this server. The first supported agent backends are Claude CLI and Codex.

The core goal is to provide a simple endpoint that can start an available agent with a supplied prompt, then return or stream the resulting output back to the caller.

## Problem

Developers often work across multiple AI coding agents, each with different strengths, availability limits, and rate windows. This project should make it possible to submit a task once and route it to the best available backend without manually switching commands or tracking every model limit by hand.

## Primary Use Case

A user on a local machine sends a prompt from the terminal to this service. The service receives the prompt, decides which configured agent backend should handle it, starts that backend on the server, and returns the result.

Example workflow:

1. User runs a terminal command with a prompt.
2. The command sends the prompt to Agent Manager.
3. Agent Manager selects an agent backend.
4. Agent Manager starts Claude CLI or Codex with the prompt.
5. Agent Manager reports the agent result back to the user.

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
- Preferred routing order.
- Per-project defaults.
- Optional fallback behavior.
- Security and execution constraints.

Configuration should be human-readable and easy to version with the project.

## Endpoint Responsibilities

The endpoint should:

- Accept a prompt or task payload.
- Accept optional routing preferences.
- Validate the request.
- Resolve the target backend.
- Start the selected agent process.
- Capture stdout, stderr, exit code, and relevant metadata.
- Return a clear success or failure response.
- Avoid leaking secrets or unrelated environment details.

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
