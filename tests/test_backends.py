from agent_manager.backends import AvailabilityState, inspect_backend
from agent_manager.config import BackendConfig


def test_inspect_backend_reports_disabled_without_path_lookup():
    availability = inspect_backend(
        BackendConfig(
            id="gemini",
            display_name="Gemini CLI",
            command="gemini",
            enabled=False,
        )
    )

    assert availability.state == AvailabilityState.DISABLED
    assert availability.executable_path is None


def test_inspect_backend_reports_missing_command():
    availability = inspect_backend(
        BackendConfig(
            id="missing-agent",
            display_name="Missing Agent",
            command="agent-manager-command-that-should-not-exist",
        )
    )

    assert availability.state == AvailabilityState.MISSING
    assert availability.reason == (
        "command not found on PATH: agent-manager-command-that-should-not-exist"
    )
