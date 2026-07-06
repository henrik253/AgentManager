import asyncio
import json
import subprocess
import sys
from pathlib import Path

from websockets.asyncio.client import connect
from websockets.asyncio.server import serve

from agent_manager.availability import AvailabilityStore
from agent_manager.config import AppConfig, BackendConfig, ServerConfig, WorkspaceConfig
from agent_manager.service import handle_session


def test_prompt_submission_streams_backend_process_events(tmp_path):
    backend_script = tmp_path / "demo_backend.py"
    backend_script.write_text(
        """
from pathlib import Path
import sys

prompt = sys.stdin.read()
Path("agent-output.txt").write_text(prompt, encoding="utf-8")
print("stdout:" + prompt.strip())
print("stderr:demo", file=sys.stderr)
""",
        encoding="utf-8",
    )
    worktree = tmp_path / "worktree"
    create_git_repo(worktree)

    async def scenario():
        config = AppConfig(
            server=ServerConfig(port=0),
            workspace=WorkspaceConfig(allow_existing_worktree=True),
            backends=(
                BackendConfig(
                    id="codex",
                    command=sys.executable,
                    args=(str(backend_script),),
                ),
            ),
        )
        availability_store = AvailabilityStore()
        async with serve(
            lambda websocket: handle_session(websocket, config, availability_store),
            "127.0.0.1",
            0,
        ) as server:
            socket = server.sockets[0]
            host, port = socket.getsockname()[:2]

            async with connect(f"ws://{host}:{port}/v1/session") as websocket:
                accepted = json.loads(await websocket.recv())
                assert accepted["type"] == "session.accepted"

                await websocket.send(
                    json.dumps(
                        {
                            "type": "prompt.submit",
                            "prompt": "Add websocket transport",
                            "backend": "codex",
                            "workspace": {
                                "mode": "existing_worktree",
                                "worktree_path": str(worktree),
                            },
                        }
                    )
                )

                routing = json.loads(await websocket.recv())
                workspace = json.loads(await websocket.recv())
                ready = json.loads(await websocket.recv())
                starting = json.loads(await websocket.recv())
                started = json.loads(await websocket.recv())
                chunks = [json.loads(await websocket.recv()), json.loads(await websocket.recv())]
                status = json.loads(await websocket.recv())
                final = json.loads(await websocket.recv())

                assert routing["type"] == "routing.decision"
                assert routing["requested_backend"] == "codex"
                assert routing["selected_backend"] == "codex"
                assert workspace["type"] == "workspace.planned"
                assert workspace["requested_worktree_path"] == str(worktree)
                assert ready["type"] == "workspace.ready"
                assert ready["worktree_path"] == str(worktree.resolve())
                assert starting["type"] == "status.update"
                assert starting["status"] == "starting"
                assert started["type"] == "process.started"
                assert {chunk["type"] for chunk in chunks} == {
                    "stdout.chunk",
                    "stderr.chunk",
                }
                assert status["type"] == "status.update"
                assert status["status"] == "completed"
                assert final["type"] == "final.success"
                assert final["exit_code"] == 0
                assert (worktree / "agent-output.txt").read_text(encoding="utf-8") == (
                    "Add websocket transport"
                )

    asyncio.run(scenario())


def test_prompt_submission_marks_backend_limited_after_process_output(tmp_path):
    backend_script = tmp_path / "limited_backend.py"
    backend_script.write_text(
        """
import sys

sys.stdin.read()
print("Codex usage limit reached. Try again in 1 hour.", file=sys.stderr)
raise SystemExit(1)
""",
        encoding="utf-8",
    )
    worktree = tmp_path / "worktree"
    create_git_repo(worktree)

    async def scenario():
        config = AppConfig(
            server=ServerConfig(port=0),
            workspace=WorkspaceConfig(allow_existing_worktree=True),
            backends=(BackendConfig(id="codex", command=sys.executable, args=(str(backend_script),)),),
        )
        availability_store = AvailabilityStore()
        async with serve(
            lambda websocket: handle_session(websocket, config, availability_store),
            "127.0.0.1",
            0,
        ) as server:
            socket = server.sockets[0]
            host, port = socket.getsockname()[:2]

            async with connect(f"ws://{host}:{port}/v1/session") as websocket:
                await websocket.recv()
                await websocket.send(
                    json.dumps(
                        {
                            "type": "prompt.submit",
                            "prompt": "hit limit",
                            "backend": "codex",
                            "workspace": {
                                "mode": "existing_worktree",
                                "worktree_path": str(worktree),
                            },
                        }
                    )
                )

                final = None
                while final is None:
                    event = json.loads(await websocket.recv())
                    if event["type"] == "final.failure":
                        final = event

                assert final["code"] == "backend_process_failed"
                assert final["temporary_limit"]["backend_id"] == "codex"
                assert availability_store.limit_for("codex") is not None

    asyncio.run(scenario())


def test_availability_list_and_reset_messages():
    async def scenario():
        config = AppConfig(
            server=ServerConfig(port=0),
            backends=(BackendConfig(id="codex", command=None),),
        )
        availability_store = AvailabilityStore()
        availability_store.record_limit("codex", reason="Codex usage limit reached")
        async with serve(
            lambda websocket: handle_session(websocket, config, availability_store),
            "127.0.0.1",
            0,
        ) as server:
            socket = server.sockets[0]
            host, port = socket.getsockname()[:2]

            async with connect(f"ws://{host}:{port}/v1/session") as websocket:
                await websocket.recv()

                await websocket.send(json.dumps({"type": "availability.list"}))
                listed = json.loads(await websocket.recv())

                assert listed["type"] == "availability.list"
                assert listed["backends"][0]["state"] == "temporarily_limited"
                assert listed["limits"][0]["backend_id"] == "codex"

                await websocket.send(
                    json.dumps({"type": "availability.reset", "backend": "codex"})
                )
                reset = json.loads(await websocket.recv())

                assert reset["type"] == "availability.reset"
                assert reset["reset_count"] == 1
                assert reset["backends"][0]["state"] == "available"

    asyncio.run(scenario())


def test_prompt_submission_skips_temporarily_limited_backend():
    async def scenario():
        config = AppConfig(
            server=ServerConfig(port=0),
            backends=(
                BackendConfig(id="claude", command=None),
                BackendConfig(id="codex", command=None),
            ),
        )
        availability_store = AvailabilityStore()
        availability_store.record_limit("claude", reason="Claude 5-hour limit reached")
        async with serve(
            lambda websocket: handle_session(websocket, config, availability_store),
            "127.0.0.1",
            0,
        ) as server:
            socket = server.sockets[0]
            host, port = socket.getsockname()[:2]

            async with connect(f"ws://{host}:{port}/v1/session") as websocket:
                await websocket.recv()

                await websocket.send(
                    json.dumps(
                        {
                            "type": "prompt.submit",
                            "prompt": "Prefer Claude but fall back",
                        }
                    )
                )

                routing = json.loads(await websocket.recv())

                assert routing["type"] == "routing.decision"
                assert routing["selected_backend"] == "codex"
                assert routing["available_backends"][0]["state"] == "temporarily_limited"

    asyncio.run(scenario())


def create_git_repo(path: Path) -> None:
    path.mkdir()
    subprocess.run(["git", "init"], cwd=path, check=True, stdout=subprocess.PIPE)
    subprocess.run(["git", "config", "user.email", "tests@example.invalid"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Tests"], cwd=path, check=True)
    (path / "README.md").write_text("test repo\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=path, check=True, stdout=subprocess.PIPE)
