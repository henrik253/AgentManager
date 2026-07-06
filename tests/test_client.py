from __future__ import annotations

from io import StringIO

import pytest

from agent_manager.client import (
    ClientOptions,
    build_prompt_submit,
    build_websocket_url,
    parse_options,
    render_event,
)


def test_parse_options_uses_prompt_arguments():
    options = parse_options(["--backend", "codex", "Fix", "tests"], stdin=StringIO(""))

    assert options.prompt == "Fix tests"
    assert options.backend == "codex"


def test_parse_options_reads_prompt_from_stdin():
    options = parse_options(["--model", "default"], stdin=StringIO("Fix from stdin\n"))

    assert options.prompt == "Fix from stdin\n"
    assert options.model == "default"


def test_parse_options_rejects_empty_prompt():
    with pytest.raises(SystemExit):
        parse_options([], stdin=StringIO("   \n"))


def test_build_websocket_url_adds_default_session_path():
    assert build_websocket_url("ws://127.0.0.1:8765", "/v1/session") == (
        "ws://127.0.0.1:8765/v1/session"
    )


def test_build_websocket_url_preserves_url_path_when_path_not_overridden():
    assert build_websocket_url("ws://127.0.0.1:8765/custom", "/v1/session") == (
        "ws://127.0.0.1:8765/custom"
    )


def test_build_prompt_submit_includes_routing_and_workspace_hints():
    message = build_prompt_submit(
        ClientOptions(
            server_url="ws://127.0.0.1:8765",
            websocket_path="/v1/session",
            prompt="Fix tests",
            backend="codex",
            model="default",
            workspace_mode="existing_worktree",
            branch="agent-task/fix-tests",
            worktree_path="../AgentManager-task",
        )
    )

    assert message == {
        "type": "prompt.submit",
        "prompt": "Fix tests",
        "backend": "codex",
        "model": "default",
        "workspace": {
            "mode": "existing_worktree",
            "branch": "agent-task/fix-tests",
            "worktree_path": "../AgentManager-task",
        },
    }


def test_render_event_prints_agent_output_cleanly():
    stdout = StringIO()
    stderr = StringIO()

    render_event(
        {"type": "stdout.chunk", "chunk": "hello\n"},
        stdout=stdout,
        stderr=stderr,
    )

    assert stdout.getvalue() == "hello\n"
    assert stderr.getvalue() == ""


def test_render_event_prints_metadata_to_stderr():
    stdout = StringIO()
    stderr = StringIO()

    render_event(
        {
            "type": "routing.decision",
            "requested_backend": None,
            "selected_backend": "codex",
            "reason": "first available backend",
        },
        stdout=stdout,
        stderr=stderr,
    )

    assert stdout.getvalue() == ""
    assert "Routing: automatic -> codex" in stderr.getvalue()


def test_render_event_json_mode_prints_raw_event_line():
    stdout = StringIO()
    stderr = StringIO()

    render_event(
        {"type": "status.update", "status": "running"},
        json_output=True,
        stdout=stdout,
        stderr=stderr,
    )

    assert stdout.getvalue() == '{"type":"status.update","status":"running"}\n'
    assert stderr.getvalue() == ""
