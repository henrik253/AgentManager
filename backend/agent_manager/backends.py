from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import shutil

from agent_manager.config import BackendConfig


class AvailabilityState(StrEnum):
    AVAILABLE = "available"
    DISABLED = "disabled"
    MISSING = "missing"


@dataclass(frozen=True)
class BackendAvailability:
    id: str
    display_name: str
    command: str | None
    enabled: bool
    state: AvailabilityState
    executable_path: str | None
    reason: str

    def to_event_payload(self) -> dict:
        return {
            "id": self.id,
            "display_name": self.display_name,
            "command": self.command,
            "enabled": self.enabled,
            "state": self.state.value,
            "executable_path": self.executable_path,
            "reason": self.reason,
        }


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
) -> dict[str, BackendAvailability]:
    return {availability.id: availability for availability in inspect_backends(backends)}
