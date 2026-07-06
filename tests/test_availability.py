from datetime import UTC, datetime, timedelta

from agent_manager.availability import (
    AvailabilityState,
    AvailabilityStore,
    BackendAvailability,
    parse_limit_message,
)


def availability(backend_id: str = "claude") -> BackendAvailability:
    return BackendAvailability(
        id=backend_id,
        display_name=backend_id,
        command=None,
        enabled=True,
        state=AvailabilityState.AVAILABLE,
        executable_path=None,
        reason="backend is available",
    )


def test_parse_claude_five_hour_limit_message():
    detected_at = datetime(2026, 7, 6, 12, 0, tzinfo=UTC)

    detection = parse_limit_message(
        "Claude 5-hour limit reached. Please try again in 2 hours.",
        detected_at=detected_at,
    )

    assert detection is not None
    assert detection.reason == "Claude 5-hour limit reached. Please try again in 2 hours."
    assert detection.retry_after == detected_at + timedelta(hours=2)


def test_parse_weekly_limit_without_retry_after():
    detection = parse_limit_message("Claude weekly limit reached for this account.")

    assert detection is not None
    assert detection.retry_after is None


def test_parse_codex_usage_limit_message():
    detection = parse_limit_message("Codex usage limit reached for this organization.")

    assert detection is not None
    assert detection.reason == "Codex usage limit reached for this organization."


def test_parse_generic_rate_limit_message():
    detected_at = datetime(2026, 7, 6, 12, 0, tzinfo=UTC)

    detection = parse_limit_message(
        "Error 429: rate limit exceeded. Retry-After: 120 seconds.",
        detected_at=detected_at,
    )

    assert detection is not None
    assert detection.retry_after == detected_at + timedelta(seconds=120)


def test_parse_non_limit_message_returns_none():
    assert parse_limit_message("authentication failed: missing API key") is None


def test_store_applies_model_specific_temporary_limit():
    now = datetime(2026, 7, 6, 12, 0, tzinfo=UTC)
    store = AvailabilityStore(clock=lambda: now)
    retry_after = datetime(2026, 7, 6, 13, 0, tzinfo=UTC)

    store.record_limit(
        "claude",
        model="pro",
        reason="Claude 5-hour limit reached",
        retry_after=retry_after,
        detected_at=now,
    )

    available_for_default = store.apply((availability("claude"),), model="default")
    limited_for_pro = store.apply((availability("claude"),), model="pro")

    assert available_for_default["claude"].state == AvailabilityState.AVAILABLE
    assert limited_for_pro["claude"].state == AvailabilityState.TEMPORARILY_LIMITED
    assert limited_for_pro["claude"].temporary_limit is not None
    assert limited_for_pro["claude"].temporary_limit.retry_after == retry_after


def test_store_expires_elapsed_retry_after():
    now = datetime(2026, 7, 6, 14, 0, tzinfo=UTC)
    store = AvailabilityStore(clock=lambda: now)
    store.record_limit(
        "codex",
        reason="Codex usage limit reached",
        retry_after=now - timedelta(minutes=1),
        detected_at=now - timedelta(hours=1),
    )

    assert store.limits() == ()
    assert (
        store.apply((availability("codex"),))["codex"].state
        == AvailabilityState.AVAILABLE
    )


def test_store_reset_removes_matching_limit():
    store = AvailabilityStore()
    store.record_limit("codex", reason="Codex usage limit reached")
    store.record_limit("gemini", reason="Gemini rate limit")

    assert store.reset(backend_id="codex") == 1

    assert [limit.backend_id for limit in store.limits()] == ["gemini"]
