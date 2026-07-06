from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path
from urllib.parse import urlsplit

from websockets.asyncio.server import ServerConnection, serve
from websockets.exceptions import ConnectionClosed

from agent_manager.availability import (
    AvailabilityStore,
    DEFAULT_AVAILABILITY_STORE,
)
from agent_manager.backends import availability_by_id
from agent_manager.config import AppConfig, load_config
from agent_manager.messages import (
    EventWriter,
    parse_client_message,
    validate_prompt_submission,
)
from agent_manager.routing import RoutingError, select_backend


LOGGER = logging.getLogger("agent_manager")


async def handle_session(
    websocket: ServerConnection,
    config: AppConfig,
    availability_store: AvailabilityStore = DEFAULT_AVAILABILITY_STORE,
) -> None:
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
                await handle_client_message(message, events, config, availability_store)
            except ValueError as exc:
                await events.send(
                    "error",
                    code="invalid_message",
                    message=str(exc),
                    recoverable=True,
                )
    except ConnectionClosed:
        LOGGER.info("websocket session closed", extra={"session_id": events.session_id})


async def handle_client_message(
    message: dict,
    events: EventWriter,
    config: AppConfig,
    availability_store: AvailabilityStore = DEFAULT_AVAILABILITY_STORE,
) -> None:
    message_type = message["type"]

    if message_type == "prompt.submit":
        submission = validate_prompt_submission(message)
        await emit_prompt_lifecycle(submission, events, config, availability_store)
        return

    if message_type == "availability.list":
        await emit_availability_list(message, events, config, availability_store)
        return

    if message_type == "availability.reset":
        await reset_availability(message, events, config, availability_store)
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


async def emit_prompt_lifecycle(
    submission: dict,
    events: EventWriter,
    config: AppConfig,
    availability_store: AvailabilityStore = DEFAULT_AVAILABILITY_STORE,
) -> None:
    backend_availability = availability_by_id(
        config.backends,
        store=availability_store,
        model=submission["model"],
    )
    try:
        routing_decision = select_backend(
            submission["backend"],
            config,
            availability=backend_availability,
        )
    except RoutingError as exc:
        await events.send(
            "error",
            code=exc.code,
            message=exc.message,
            recoverable=True,
        )
        await events.send("final.failure", code=exc.code, exit_code=None)
        return

    requested_availability = backend_availability.get(submission["backend"])
    selected_availability = backend_availability.get(routing_decision.selected_backend)
    await events.send(
        "routing.decision",
        requested_backend=routing_decision.requested_backend,
        requested_model=submission["model"],
        selected_backend=routing_decision.selected_backend,
        requested_backend_metadata=(
            requested_availability.to_event_payload()
            if requested_availability is not None
            else None
        ),
        selected_backend_metadata=(
            selected_availability.to_event_payload()
            if selected_availability is not None
            else None
        ),
        available_backends=[
            availability.to_event_payload()
            for availability in backend_availability.values()
            if availability.enabled
        ],
        reason=routing_decision.reason,
    )
    workspace = submission["workspace"] or {}
    await events.send(
        "workspace.planned",
        mode=workspace.get("mode", "create_worktree"),
        requested_branch=workspace.get("branch"),
        requested_worktree_path=workspace.get("worktree_path"),
        worktree_root=config.workspace.worktree_root,
        branch_prefix=config.workspace.branch_prefix,
        allow_existing_worktree=config.workspace.allow_existing_worktree,
        reason="worktree creation is scheduled for a later phase",
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


async def emit_availability_list(
    message: dict,
    events: EventWriter,
    config: AppConfig,
    availability_store: AvailabilityStore,
) -> None:
    backend_filter = _optional_string_field(message, "backend")
    model_filter = _optional_string_field(message, "model")
    backend_availability = availability_by_id(
        config.backends,
        store=availability_store,
        model=model_filter,
    )
    await events.send(
        "availability.list",
        backend=backend_filter,
        model=model_filter,
        backends=[
            availability.to_event_payload()
            for availability in backend_availability.values()
            if backend_filter is None or availability.id == backend_filter
        ],
        limits=[
            limit.to_event_payload()
            for limit in availability_store.limits(
                backend_id=backend_filter,
                model=model_filter,
            )
        ],
    )


async def reset_availability(
    message: dict,
    events: EventWriter,
    config: AppConfig,
    availability_store: AvailabilityStore,
) -> None:
    backend_filter = _optional_string_field(message, "backend")
    model_filter = _optional_string_field(message, "model")
    reset_count = availability_store.reset(backend_id=backend_filter, model=model_filter)
    backend_availability = availability_by_id(
        config.backends,
        store=availability_store,
        model=model_filter,
    )
    await events.send(
        "availability.reset",
        backend=backend_filter,
        model=model_filter,
        reset_count=reset_count,
        backends=[
            availability.to_event_payload()
            for availability in backend_availability.values()
            if backend_filter is None or availability.id == backend_filter
        ],
    )


def _optional_string_field(message: dict, field: str) -> str | None:
    value = message.get(field)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string when provided")
    stripped = value.strip()
    return stripped or None


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
        default=None,
        help="Path to the Agent Manager TOML config file. Defaults to project discovery.",
    )
    return parser


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    args = build_parser().parse_args()
    config = load_config(args.config)
    try:
        asyncio.run(run_server(config))
    except KeyboardInterrupt:
        LOGGER.info("websocket server stopped")
