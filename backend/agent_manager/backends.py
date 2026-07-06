from __future__ import annotations

import shutil

from agent_manager.availability import (
    AvailabilityState,
    AvailabilityStore,
    BackendAvailability,
)
from agent_manager.config import BackendConfig


def inspect_backend(backend: BackendConfig) -> BackendAvailability:
    if not backend.enabled:
        return BackendAvailability(
            id=backend.id,
            display_name=backend.display_name or backend.id,
            command=backend.command,
            enabled=False,
            state=AvailabilityState.DISABLED,
            executable_path=None,
            reason="backend is disabled by configuration",
        )

    if backend.command is None:
        return BackendAvailability(
            id=backend.id,
            display_name=backend.display_name or backend.id,
            command=None,
            enabled=True,
            state=AvailabilityState.AVAILABLE,
            executable_path=None,
            reason="no command configured; treating backend as available",
        )

    executable_path = shutil.which(backend.command)
    if executable_path is None:
        return BackendAvailability(
            id=backend.id,
            display_name=backend.display_name or backend.id,
            command=backend.command,
            enabled=True,
            state=AvailabilityState.MISSING,
            executable_path=None,
            reason=f"command not found on PATH: {backend.command}",
        )

    return BackendAvailability(
        id=backend.id,
        display_name=backend.display_name or backend.id,
        command=backend.command,
        enabled=True,
        state=AvailabilityState.AVAILABLE,
        executable_path=executable_path,
        reason="command found on PATH",
    )


def inspect_backends(backends: tuple[BackendConfig, ...]) -> tuple[BackendAvailability, ...]:
    return tuple(inspect_backend(backend) for backend in backends)


def availability_by_id(
    backends: tuple[BackendConfig, ...],
    *,
    store: AvailabilityStore | None = None,
    model: str | None = None,
) -> dict[str, BackendAvailability]:
    availability = inspect_backends(backends)
    if store is not None:
        return store.apply(availability, model=model)
    return {entry.id: entry for entry in availability}
