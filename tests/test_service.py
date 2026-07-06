import asyncio
import json

from websockets.asyncio.client import connect
from websockets.asyncio.server import serve

from agent_manager.availability import AvailabilityStore
from agent_manager.config import AppConfig, BackendConfig, ServerConfig
from agent_manager.service import handle_session


def test_prompt_submission_streams_session_events():
    async def scenario():
        config = AppConfig(
            server=ServerConfig(port=0),
            backends=(BackendConfig(id="codex", command=None),),
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
                                "mode": "create_worktree",
                                "branch": "agent-task/websocket-transport",
                            },
                        }
                    )
                )

                routing = json.loads(await websocket.recv())
                workspace = json.loads(await websocket.recv())
                status = json.loads(await websocket.recv())
                final = json.loads(await websocket.recv())

                assert routing["type"] == "routing.decision"
                assert routing["requested_backend"] == "codex"
                assert routing["selected_backend"] == "codex"
                assert workspace["type"] == "workspace.planned"
                assert workspace["requested_branch"] == "agent-task/websocket-transport"
                assert status["type"] == "status.update"
                assert final["type"] == "final.failure"
                assert final["code"] == "backend_execution_not_implemented"

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
