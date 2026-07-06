from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Mapping, TextIO
from urllib.parse import urlsplit, urlunsplit

from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed, WebSocketException


DEFAULT_SERVER_URL = "ws://127.0.0.1:8765"
DEFAULT_WEBSOCKET_PATH = "/v1/session"
ENV_PREFIX = "AGENT_MANAGER_"

EXIT_SUCCESS = 0
EXIT_FAILURE = 1
EXIT_PROTOCOL_ERROR = 2
EXIT_USAGE = 64
EXIT_TIMEOUT = 124


@dataclass(frozen=True)
class ClientOptions:
    server_url: str
    websocket_path: str
    prompt: str
    backend: str | None = None
    model: str | None = None
    workspace_mode: str | None = None
    branch: str | None = None
    worktree_path: str | None = None
    json_output: bool = False
    timeout: float | None = None


def build_parser() -> argparse.ArgumentParser:
    server_url = default_server_url(os.environ)
    websocket_path = os.environ.get(
        f"{ENV_PREFIX}WEBSOCKET_PATH",
        DEFAULT_WEBSOCKET_PATH,
    )
    parser = argparse.ArgumentParser(
        description="Submit a prompt to the local Agent Manager websocket server."
    )
    parser.add_argument(
        "--url",
        default=server_url,
        help=f"Server websocket base URL. Defaults to {server_url}.",
    )
    parser.add_argument(
        "--path",
        default=websocket_path,
        help=f"Websocket session path. Defaults to {websocket_path}.",
    )
    parser.add_argument(
        "--backend",
        default=os.environ.get(f"{ENV_PREFIX}BACKEND"),
        help="Backend id override, such as codex.",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get(f"{ENV_PREFIX}MODEL"),
        help="Model or tier override for the selected backend.",
    )
    parser.add_argument(
        "--workspace-mode",
        choices=("create_worktree", "existing_worktree"),
        help="Workspace mode hint for the task.",
    )
    parser.add_argument("--branch", help="Branch name hint for task workspace creation.")
    parser.add_argument("--worktree-path", help="Existing worktree path hint.")
    parser.add_argument(
        "--json",
        action="store_true",
        default=parse_env_bool(os.environ.get(f"{ENV_PREFIX}JSON")),
        help="Print raw server events as newline-delimited JSON.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=default_timeout(os.environ),
        help="Maximum seconds to wait for a final event.",
    )
    parser.add_argument(
        "prompt",
        nargs="*",
        help="Prompt text. When omitted, the prompt is read from stdin.",
    )
    return parser


def default_server_url(env: Mapping[str, str]) -> str:
    server_url = env.get(f"{ENV_PREFIX}SERVER_URL")
    if server_url:
        return server_url
    host = env.get(f"{ENV_PREFIX}HOST", "127.0.0.1")
    port = env.get(f"{ENV_PREFIX}PORT", "8765")
    return f"ws://{host}:{port}"


def default_timeout(env: Mapping[str, str]) -> float | None:
    value = env.get(f"{ENV_PREFIX}CONNECT_TIMEOUT")
    if value is None or not value.strip():
        return None
    return float(value)


def parse_env_bool(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def parse_options(
    argv: Sequence[str] | None = None, stdin: TextIO | None = None
) -> ClientOptions:
    parser = build_parser()
    args = parser.parse_args(argv)
    prompt = prompt_from_args(args.prompt, stdin or sys.stdin)
    if not prompt.strip():
        parser.error("prompt is required as arguments or stdin")

    return ClientOptions(
        server_url=args.url,
        websocket_path=args.path,
        prompt=prompt,
        backend=args.backend,
        model=args.model,
        workspace_mode=args.workspace_mode,
        branch=args.branch,
        worktree_path=args.worktree_path,
        json_output=args.json,
        timeout=args.timeout,
    )


def prompt_from_args(prompt_args: Sequence[str], stdin: TextIO) -> str:
    if prompt_args:
        return " ".join(prompt_args)
    return stdin.read()


def build_websocket_url(server_url: str, websocket_path: str) -> str:
    parsed = urlsplit(server_url)
    if parsed.scheme not in {"ws", "wss"}:
        raise ValueError("--url must use ws:// or wss://")
    if not parsed.netloc:
        raise ValueError("--url must include a host")
    if not websocket_path.startswith("/"):
        raise ValueError("--path must start with '/'")

    path = parsed.path
    if path in {"", "/"}:
        path = websocket_path
    elif websocket_path != DEFAULT_WEBSOCKET_PATH:
        path = websocket_path

    return urlunsplit((parsed.scheme, parsed.netloc, path, parsed.query, parsed.fragment))


def build_prompt_submit(options: ClientOptions) -> dict[str, Any]:
    message: dict[str, Any] = {
        "type": "prompt.submit",
        "prompt": options.prompt,
    }
    if options.backend:
        message["backend"] = options.backend
    if options.model:
        message["model"] = options.model

    workspace = {
        key: value
        for key, value in {
            "mode": options.workspace_mode,
            "branch": options.branch,
            "worktree_path": options.worktree_path,
        }.items()
        if value is not None
    }
    if workspace:
        message["workspace"] = workspace

    return message


async def run_client(options: ClientOptions) -> int:
    url = build_websocket_url(options.server_url, options.websocket_path)
    try:
        if options.timeout is None:
            return await run_client_session(url, options)
        async with asyncio.timeout(options.timeout):
            return await run_client_session(url, options)
    except TimeoutError:
        print(f"Timed out after {options.timeout:g} seconds", file=sys.stderr)
        return EXIT_TIMEOUT
    except (OSError, ValueError, WebSocketException) as exc:
        print(f"Connection error: {exc}", file=sys.stderr)
        return EXIT_PROTOCOL_ERROR


async def run_client_session(url: str, options: ClientOptions) -> int:
    async with connect(url) as websocket:
        await websocket.send(json.dumps(build_prompt_submit(options), separators=(",", ":")))

        try:
            async for raw_event in websocket:
                event = parse_server_event(raw_event)
                render_event(event, json_output=options.json_output)
                event_type = event.get("type")
                if event_type == "final.success":
                    return EXIT_SUCCESS
                if event_type == "final.failure":
                    return failure_exit_code(event)
        except ConnectionClosed as exc:
            print(f"Connection closed before final event: {exc}", file=sys.stderr)
            return EXIT_PROTOCOL_ERROR

    print("Connection closed before final event", file=sys.stderr)
    return EXIT_PROTOCOL_ERROR


def parse_server_event(raw_event: str | bytes) -> dict[str, Any]:
    if isinstance(raw_event, bytes):
        raise ValueError("server sent unsupported binary event")
    event = json.loads(raw_event)
    if not isinstance(event, dict):
        raise ValueError("server event must be a JSON object")
    event_type = event.get("type")
    if not isinstance(event_type, str) or not event_type:
        raise ValueError("server event.type is required")
    return event


def render_event(
    event: dict[str, Any],
    *,
    json_output: bool = False,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> None:
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    if json_output:
        print(json.dumps(event, separators=(",", ":")), file=stdout, flush=True)
        return

    event_type = event["type"]
    if event_type == "stdout.chunk":
        print(str(event.get("chunk", event.get("data", ""))), end="", file=stdout, flush=True)
    elif event_type == "stderr.chunk":
        print(str(event.get("chunk", event.get("data", ""))), end="", file=stderr, flush=True)
    elif event_type == "routing.decision":
        render_routing_decision(event, stderr)
    elif event_type == "workspace.planned":
        render_workspace_plan(event, stderr)
    elif event_type == "status.update":
        render_status_update(event, stderr)
    elif event_type == "error":
        print(
            f"Error: {event.get('code', 'unknown')}: {event.get('message', '')}",
            file=stderr,
            flush=True,
        )
    elif event_type == "final.success":
        print("Completed successfully", file=stderr, flush=True)
    elif event_type == "final.failure":
        code = event.get("code", "failed")
        print(f"Failed: {code}", file=stderr, flush=True)
    elif event_type == "session.accepted":
        print(
            f"Connected: session {event.get('session_id', 'unknown')}",
            file=stderr,
            flush=True,
        )


def render_routing_decision(event: dict[str, Any], stderr: TextIO) -> None:
    selected = event.get("selected_backend") or "unknown"
    requested = event.get("requested_backend") or "automatic"
    reason = event.get("reason")
    line = f"Routing: {requested} -> {selected}"
    if reason:
        line = f"{line} ({reason})"
    print(line, file=stderr, flush=True)


def render_workspace_plan(event: dict[str, Any], stderr: TextIO) -> None:
    parts = [f"mode={event.get('mode', 'unknown')}"]
    if event.get("requested_branch"):
        parts.append(f"branch={event['requested_branch']}")
    if event.get("requested_worktree_path"):
        parts.append(f"worktree={event['requested_worktree_path']}")
    print(f"Workspace: {', '.join(parts)}", file=stderr, flush=True)


def render_status_update(event: dict[str, Any], stderr: TextIO) -> None:
    status = event.get("status", "unknown")
    detail = event.get("detail")
    line = f"Status: {status}"
    if detail:
        line = f"{line} - {detail}"
    print(line, file=stderr, flush=True)


def failure_exit_code(event: dict[str, Any]) -> int:
    exit_code = event.get("exit_code")
    if isinstance(exit_code, int) and exit_code != 0:
        return exit_code
    return EXIT_FAILURE


def main(argv: Sequence[str] | None = None) -> None:
    try:
        options = parse_options(argv)
        raise SystemExit(asyncio.run(run_client(options)))
    except KeyboardInterrupt:
        raise SystemExit(130) from None
