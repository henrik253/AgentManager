import asyncio
import json

from websockets.asyncio.client import connect
from websockets.asyncio.server import serve

from agent_manager.config import AppConfig, ServerConfig
from agent_manager.service import handle_session


def test_prompt_submission_streams_session_events():
    async def scenario():
        config = AppConfig(server=ServerConfig(port=0))
        async with serve(
            lambda websocket: handle_session(websocket, config),
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
                        }
                    )
                )

                routing = json.loads(await websocket.recv())
                status = json.loads(await websocket.recv())
                final = json.loads(await websocket.recv())

                assert routing["type"] == "routing.decision"
                assert routing["requested_backend"] == "codex"
                assert status["type"] == "status.update"
                assert final["type"] == "final.failure"
                assert final["code"] == "backend_execution_not_implemented"

    asyncio.run(scenario())
