from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path
from urllib.parse import urlsplit

from websockets.asyncio.server import ServerConnection, serve
from websockets.exceptions import ConnectionClosed

from agent_manager.config import AppConfig, DEFAULT_CONFIG_PATH, load_config
from agent_manager.messages import (
    EventWriter,
    parse_client_message,
    validate_prompt_submission,
)


LOGGER = logging.getLogger("agent_manager")


async def handle_session(websocket: ServerConnection, config: AppConfig) -> None:
    request_path = urlsplit(websocket.request.path if websocket.request else "").path
    if request_path != config.server.websocket_path:
        await websocket.close(code=1008, reason="unsupported websocket path")
        return

    events = EventWriter(websocket)
    await events.send("session.accepted", websocket_path=config.server.websocket_path)

    try:
        async for raw_message in websocket:
            try:
                message = parse_client_message(raw_message)
                await handle_client_message(message, events)
            except ValueError as exc:
                await events.send(
                    "error",
                    code="invalid_message",
                    message=str(exc),
                    recoverable=True,
                )
    except ConnectionClosed:
        LOGGER.info("websocket session closed", extra={"session_id": events.session_id})


async def handle_client_message(message: dict, events: EventWriter) -> None:
    message_type = message["type"]

    if message_type == "prompt.submit":
        submission = validate_prompt_submission(message)
        await emit_prompt_lifecycle(submission, events)
        return

    if message_type == "session.cancel":
        await events.send("status.update", status="cancelled")
        await events.send("final.failure", code="cancelled", exit_code=None)
        return

    await events.send(
        "error",
        code="unknown_message_type",
        message=f"unsupported message type: {message_type}",
        recoverable=True,
    )


async def emit_prompt_lifecycle(submission: dict, events: EventWriter) -> None:
    requested_backend = submission["backend"] or "automatic"
    await events.send(
        "routing.decision",
        requested_backend=requested_backend,
        requested_model=submission["model"],
        selected_backend=None,
        reason="backend routing is scheduled for phase 3",
    )
    await events.send(
        "status.update",
        status="waiting_for_backend_execution",
        detail="persistent websocket transport is ready; backend execution is not implemented yet",
    )
    await events.send(
        "final.failure",
        code="backend_execution_not_implemented",
        exit_code=None,
    )


async def run_server(config: AppConfig) -> None:
    LOGGER.info(
        "starting websocket server on %s:%s%s",
        config.server.host,
        config.server.port,
        config.server.websocket_path,
    )
    async with serve(
        lambda websocket: handle_session(websocket, config),
        config.server.host,
        config.server.port,
        max_size=config.server.max_message_size,
    ) as server:
        await server.serve_forever()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Agent Manager websocket server.")
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="Path to the Agent Manager TOML config file.",
    )
    return parser


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    args = build_parser().parse_args()
    config = load_config(args.config)
    asyncio.run(run_server(config))
