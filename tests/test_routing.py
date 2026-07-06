import pytest

from agent_manager.config import AppConfig, BackendConfig, RoutingConfig, load_config
from agent_manager.routing import (
    AvailabilityState,
    BackendAvailability,
    RoutingError,
    discover_backend_availability,
    select_backend,
)


def app_config(
    *,
    routing: RoutingConfig | None = None,
    backends: tuple[BackendConfig, ...] | None = None,
) -> AppConfig:
    return AppConfig(
        routing=routing or RoutingConfig(preferred_backends=("claude", "codex")),
        backends=backends
        or (
            BackendConfig(id="claude", command="claude"),
            BackendConfig(id="codex", command="codex"),
            BackendConfig(id="gemini", command="gemini"),
        ),
    )


def backend_availability(
    backend_id: str,
    state: AvailabilityState = AvailabilityState.AVAILABLE,
    reason: str = "backend is available",
) -> BackendAvailability:
    return BackendAvailability(
        id=backend_id,
        display_name=backend_id,
        command=None,
        enabled=state != AvailabilityState.DISABLED,
        state=state,
        executable_path=None,
        reason=reason,
    )


def test_explicit_backend_selection_requires_known_backend():
    with pytest.raises(RoutingError) as exc:
        select_backend(
            "missing",
            app_config(),
            availability={"codex": backend_availability("codex")},
        )

    assert exc.value.code == "unknown_backend"


def test_explicit_backend_selection_requires_available_backend():
    with pytest.raises(RoutingError) as exc:
        select_backend(
            "codex",
            app_config(),
            availability={
                "codex": backend_availability(
                    "codex", AvailabilityState.MISSING, "codex was not found"
                )
            },
        )

    assert exc.value.code == "backend_unavailable"
    assert "codex was not found" in exc.value.message


def test_explicit_backend_selection_returns_reason():
    decision = select_backend(
        "codex",
        app_config(),
        availability={"codex": backend_availability("codex")},
    )

    assert decision.requested_backend == "codex"
    assert decision.selected_backend == "codex"
    assert "explicit backend 'codex'" in decision.reason


def test_automatic_selection_uses_first_available_preferred_backend():
    decision = select_backend(
        None,
        app_config(),
        availability={
            "claude": backend_availability(
                "claude",
                AvailabilityState.TEMPORARILY_LIMITED,
                "temporary limit reached",
            ),
            "codex": backend_availability("codex"),
        },
    )

    assert decision.requested_backend == "automatic"
    assert decision.selected_backend == "codex"
    assert "first available preferred backend" in decision.reason


def test_automatic_selection_can_use_default_backend_after_preferred():
    decision = select_backend(
        None,
        app_config(
            routing=RoutingConfig(
                preferred_backends=("claude",),
                allow_fallback=False,
                default_backend="gemini",
            )
        ),
        availability={
            "claude": backend_availability(
                "claude", AvailabilityState.MISSING, "claude was not found"
            ),
            "gemini": backend_availability("gemini"),
        },
    )

    assert decision.selected_backend == "gemini"
    assert "default backend 'gemini'" in decision.reason


def test_automatic_selection_respects_disabled_fallback():
    with pytest.raises(RoutingError) as exc:
        select_backend(
            None,
            app_config(
                routing=RoutingConfig(
                    preferred_backends=("claude",), allow_fallback=False
                )
            ),
            availability={
                "claude": backend_availability(
                    "claude", AvailabilityState.MISSING, "claude was not found"
                ),
                "codex": backend_availability("codex"),
            },
        )

    assert exc.value.code == "no_available_backend"


def test_automatic_selection_uses_fallback_when_allowed():
    decision = select_backend(
        None,
        app_config(routing=RoutingConfig(preferred_backends=("claude",))),
        availability={
            "claude": backend_availability(
                "claude", AvailabilityState.MISSING, "claude was not found"
            ),
            "codex": backend_availability("codex"),
        },
    )

    assert decision.selected_backend == "codex"
    assert "fallback backend 'codex'" in decision.reason


def test_explicit_mode_requires_backend_without_default():
    with pytest.raises(RoutingError) as exc:
        select_backend(
            None,
            app_config(routing=RoutingConfig(mode="explicit")),
            availability={"codex": backend_availability("codex")},
        )

    assert exc.value.code == "backend_required"


def test_disabled_backend_is_unavailable():
    availability = discover_backend_availability(
        BackendConfig(id="codex", command="codex", enabled=False)
    )

    assert not availability.is_available
    assert availability.state == "disabled"


def test_load_config_parses_routing_and_backends(tmp_path):
    config_path = tmp_path / "agent-manager.toml"
    config_path.write_text(
        """
[routing]
mode = "automatic"
preferred_backends = ["claude", "codex"]
allow_fallback = false
default_backend = "codex"

[[backends]]
id = "claude"
display_name = "Claude CLI"
command = "claude"
enabled = false

[[backends]]
id = "codex"
display_name = "Codex"
command = "codex"
enabled = true
""",
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.routing.mode == "automatic"
    assert config.routing.preferred_backends == ("claude", "codex")
    assert not config.routing.allow_fallback
    assert config.routing.default_backend == "codex"
    assert [backend.id for backend in config.backends] == ["claude", "codex"]
    assert not config.backends[0].enabled
