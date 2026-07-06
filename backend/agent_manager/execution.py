from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from agent_manager.config import BackendConfig


class EventSender(Protocol):
    def __call__(self, event_type: str, **payload: Any) -> Awaitable[None]:
        ...


class BackendExecutionError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class BackendExecutionResult:
    backend_id: str
    command: tuple[str, ...]
    cwd: Path
    exit_code: int
    duration_seconds: float
    stdout: str
    stderr: str

    @property
    def succeeded(self) -> bool:
        return self.exit_code == 0


async def run_backend_process(
    backend: BackendConfig,
    *,
    prompt: str,
    cwd: Path,
    send_event: EventSender,
) -> BackendExecutionResult:
    if not backend.command:
        raise BackendExecutionError(
            "backend_command_not_configured",
            f"backend {backend.id} has no command configured",
        )

    argv = (backend.command, *backend.args)
    start = time.monotonic()
    try:
        process = await asyncio.create_subprocess_exec(
            *argv,
            cwd=str(cwd),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except OSError as exc:
        raise BackendExecutionError(
            "backend_process_start_failed",
            f"failed to start backend process: {exc}",
        ) from exc

    await send_event(
        "process.started",
        backend=backend.id,
        command=backend.command,
        args=list(backend.args),
        pid=process.pid,
        cwd=str(cwd),
    )

    assert process.stdin is not None
    process.stdin.write(prompt.encode("utf-8"))
    await process.stdin.drain()
    process.stdin.close()
    await process.stdin.wait_closed()

    stdout_parts: list[str] = []
    stderr_parts: list[str] = []
    await asyncio.gather(
        stream_reader(
            process.stdout,
            event_type="stdout.chunk",
            backend_id=backend.id,
            cwd=cwd,
            parts=stdout_parts,
            send_event=send_event,
        ),
        stream_reader(
            process.stderr,
            event_type="stderr.chunk",
            backend_id=backend.id,
            cwd=cwd,
            parts=stderr_parts,
            send_event=send_event,
        ),
    )
    exit_code = await process.wait()
    duration_seconds = time.monotonic() - start
    return BackendExecutionResult(
        backend_id=backend.id,
        command=argv,
        cwd=cwd,
        exit_code=exit_code,
        duration_seconds=duration_seconds,
        stdout="".join(stdout_parts),
        stderr="".join(stderr_parts),
    )


async def stream_reader(
    reader: asyncio.StreamReader | None,
    *,
    event_type: str,
    backend_id: str,
    cwd: Path,
    parts: list[str],
    send_event: EventSender,
) -> None:
    if reader is None:
        return
    stream = "stdout" if event_type == "stdout.chunk" else "stderr"
    while True:
        chunk = await reader.read(4096)
        if not chunk:
            break
        text = chunk.decode("utf-8", errors="replace")
        parts.append(text)
        await send_event(
            event_type,
            backend=backend_id,
            stream=stream,
            chunk=text,
            cwd=str(cwd),
        )
