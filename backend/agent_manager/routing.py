from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from agent_manager.availability import AvailabilityState, BackendAvailability
from agent_manager.backends import availability_by_id
from agent_manager.config import AppConfig, BackendConfig


AVAILABLE = AvailabilityState.AVAILABLE.value
DISABLED = AvailabilityState.DISABLED.value
MISSING = AvailabilityState.MISSING.value
TEMPORARILY_LIMITED = AvailabilityState.TEMPORARILY_LIMITED.value
FAILED_HEALTH_CHECK = AvailabilityState.FAILED_HEALTH_CHECK.value
UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class RoutingDecision:
    requested_backend: str
    selected_backend: str
    reason: str


class RoutingError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def select_backend(
    requested_backend: str | None,
    config: AppConfig,
    availability: Mapping[str, BackendAvailability] | None = None,
) -> RoutingDecision:
    backends = {backend.id: backend for backend in config.backends}
    requested = normalize_requested_backend(requested_backend)
    availability_by_id = (
        availability if availability is not None else discover_availability(config.backends)
    )

    if requested:
        backend = backends.get(requested)
        if backend is None:
            raise RoutingError("unknown_backend", f"unknown backend requested: {requested}")
        ensure_available(requested, availability_by_id)
        return RoutingDecision(
            requested_backend=requested,
            selected_backend=requested,
            reason=f"explicit backend '{requested}' was requested and is available",
        )

    if config.routing.mode == "explicit":
        if config.routing.default_backend:
            selected = config.routing.default_backend
            if selected not in backends:
                raise RoutingError(
                    "unknown_default_backend",
                    f"configured default backend is unknown: {selected}",
                )
            ensure_available(selected, availability_by_id)
            return RoutingDecision(
                requested_backend="automatic",
                selected_backend=selected,
                reason=f"default backend '{selected}' selected because routing mode is explicit",
            )

        raise RoutingError(
            "backend_required",
            "routing mode is explicit and no backend was requested",
        )

    for backend_id in config.routing.preferred_backends:
        if backend_id not in backends:
            raise RoutingError(
                "unknown_preferred_backend",
                f"configured preferred backend is unknown: {backend_id}",
            )
        if is_available(backend_id, availability_by_id):
            return RoutingDecision(
                requested_backend="automatic",
                selected_backend=backend_id,
                reason=f"selected first available preferred backend '{backend_id}'",
            )

    if config.routing.default_backend:
        selected = config.routing.default_backend
        if selected not in backends:
            raise RoutingError(
                "unknown_default_backend",
                f"configured default backend is unknown: {selected}",
            )
        if is_available(selected, availability_by_id):
            return RoutingDecision(
                requested_backend="automatic",
                selected_backend=selected,
                reason=f"selected default backend '{selected}' after preferred backends were unavailable",
            )

    if config.routing.allow_fallback:
        preferred = set(config.routing.preferred_backends)
        default = config.routing.default_backend
        for backend in config.backends:
            if backend.id in preferred or backend.id == default:
                continue
            if is_available(backend.id, availability_by_id):
                return RoutingDecision(
                    requested_backend="automatic",
                    selected_backend=backend.id,
                    reason=f"selected fallback backend '{backend.id}' because preferred backends were unavailable",
                )

    raise RoutingError(
        "no_available_backend",
        "no configured backend is available for automatic routing",
    )


def normalize_requested_backend(requested_backend: str | None) -> str | None:
    if requested_backend is None:
        return None
    normalized = requested_backend.strip()
    if not normalized or normalized == "automatic":
        return None
    return normalized


def ensure_available(
    backend_id: str, availability: Mapping[str, BackendAvailability]
) -> None:
    backend_availability = availability.get(
        backend_id, unknown_backend_availability(backend_id)
    )
    if backend_availability.is_available:
        return

    raise RoutingError(
        "backend_unavailable",
        f"backend '{backend_id}' is unavailable: {backend_availability.reason}",
    )


def is_available(
    backend_id: str, availability: Mapping[str, BackendAvailability]
) -> bool:
    return availability.get(backend_id, unknown_backend_availability(backend_id)).is_available


def discover_availability(
    backends: tuple[BackendConfig, ...],
) -> dict[str, BackendAvailability]:
    return availability_by_id(backends)


def discover_backend_availability(backend: BackendConfig) -> BackendAvailability:
    return availability_by_id((backend,))[backend.id]


def unknown_backend_availability(backend_id: str) -> BackendAvailability:
    return BackendAvailability(
        id=backend_id,
        display_name=backend_id,
        command=None,
        enabled=False,
        state=AvailabilityState.MISSING,
        executable_path=None,
        reason="backend availability is unknown",
    )
