from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
import re
from typing import Callable, Iterable


class AvailabilityState(StrEnum):
    AVAILABLE = "available"
    MISSING = "missing"
    TEMPORARILY_LIMITED = "temporarily_limited"
    FAILED_HEALTH_CHECK = "failed_health_check"
    DISABLED = "disabled"


@dataclass(frozen=True)
class TemporaryLimitState:
    backend_id: str
    model: str | None
    reason: str
    first_detected: datetime
    retry_after: datetime | None = None

    def to_event_payload(self) -> dict:
        return {
            "backend_id": self.backend_id,
            "model": self.model,
            "reason": self.reason,
            "first_detected": self.first_detected.isoformat(),
            "retry_after": self.retry_after.isoformat()
            if self.retry_after is not None
            else None,
        }


@dataclass(frozen=True)
class LimitDetection:
    reason: str
    retry_after: datetime | None = None


@dataclass(frozen=True)
class LimitKey:
    backend_id: str
    model: str | None = None


@dataclass(frozen=True)
class BackendAvailability:
    id: str
    display_name: str
    command: str | None
    enabled: bool
    state: AvailabilityState
    executable_path: str | None
    reason: str
    temporary_limit: TemporaryLimitState | None = None

    @property
    def is_available(self) -> bool:
        return self.state == AvailabilityState.AVAILABLE

    def with_temporary_limit(self, limit: TemporaryLimitState) -> BackendAvailability:
        return BackendAvailability(
            id=self.id,
            display_name=self.display_name,
            command=self.command,
            enabled=self.enabled,
            state=AvailabilityState.TEMPORARILY_LIMITED,
            executable_path=self.executable_path,
            reason=limit.reason,
            temporary_limit=limit,
        )

    def to_event_payload(self) -> dict:
        return {
            "id": self.id,
            "display_name": self.display_name,
            "command": self.command,
            "enabled": self.enabled,
            "state": self.state.value,
            "executable_path": self.executable_path,
            "reason": self.reason,
            "temporary_limit": (
                self.temporary_limit.to_event_payload()
                if self.temporary_limit is not None
                else None
            ),
        }


class AvailabilityStore:
    def __init__(self, clock: Callable[[], datetime] | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))
        self._limits: dict[LimitKey, TemporaryLimitState] = {}

    def record_limit(
        self,
        backend_id: str,
        *,
        model: str | None = None,
        reason: str,
        retry_after: datetime | None = None,
        detected_at: datetime | None = None,
    ) -> TemporaryLimitState:
        now = detected_at or self._clock()
        key = LimitKey(backend_id=backend_id, model=model)
        existing = self._limits.get(key)
        limit = TemporaryLimitState(
            backend_id=backend_id,
            model=model,
            reason=reason,
            first_detected=existing.first_detected if existing else now,
            retry_after=retry_after,
        )
        self._limits[key] = limit
        return limit

    def record_limit_message(
        self,
        backend_id: str,
        message: str,
        *,
        model: str | None = None,
        detected_at: datetime | None = None,
    ) -> TemporaryLimitState | None:
        now = detected_at or self._clock()
        detection = parse_limit_message(message, detected_at=now)
        if detection is None:
            return None
        return self.record_limit(
            backend_id,
            model=model,
            reason=detection.reason,
            retry_after=detection.retry_after,
            detected_at=now,
        )

    def reset(
        self, *, backend_id: str | None = None, model: str | None = None
    ) -> int:
        keys = [
            key
            for key in self._limits
            if (backend_id is None or key.backend_id == backend_id)
            and (model is None or key.model == model)
        ]
        for key in keys:
            del self._limits[key]
        return len(keys)

    def limits(
        self, *, backend_id: str | None = None, model: str | None = None
    ) -> tuple[TemporaryLimitState, ...]:
        self._expire_elapsed_limits()
        return tuple(
            limit
            for key, limit in self._limits.items()
            if (backend_id is None or key.backend_id == backend_id)
            and (model is None or key.model == model)
        )

    def limit_for(
        self, backend_id: str, *, model: str | None = None
    ) -> TemporaryLimitState | None:
        self._expire_elapsed_limits()
        return self._limits.get(LimitKey(backend_id, model)) or self._limits.get(
            LimitKey(backend_id, None)
        )

    def apply(
        self,
        availability: Iterable[BackendAvailability],
        *,
        model: str | None = None,
    ) -> dict[str, BackendAvailability]:
        self._expire_elapsed_limits()
        result: dict[str, BackendAvailability] = {}
        for backend in availability:
            limit = self.limit_for(backend.id, model=model)
            if backend.is_available and limit is not None:
                result[backend.id] = backend.with_temporary_limit(limit)
            else:
                result[backend.id] = backend
        return result

    def _expire_elapsed_limits(self) -> None:
        now = self._clock()
        expired = [
            key
            for key, limit in self._limits.items()
            if limit.retry_after is not None and limit.retry_after <= now
        ]
        for key in expired:
            del self._limits[key]


_LIMIT_PATTERNS = (
    re.compile(r"\b(?:5|five)[ -]?hour\b.*\blimit\b", re.IGNORECASE),
    re.compile(r"\bweekly\b.*\blimit\b", re.IGNORECASE),
    re.compile(r"\busage limit\b", re.IGNORECASE),
    re.compile(r"\brate limit(?:ed)?\b", re.IGNORECASE),
    re.compile(r"\btoo many requests\b", re.IGNORECASE),
    re.compile(r"\bquota exceeded\b", re.IGNORECASE),
    re.compile(r"\b429\b"),
)

_DURATION_RE = re.compile(
    r"(?:retry(?:-after)?|try again|reset(?:s)?|available again)[^\n\r]{0,40}?"
    r"(?:in|after|:)?\s*(?P<amount>\d+)\s*"
    r"(?P<unit>second|seconds|minute|minutes|hour|hours|day|days)",
    re.IGNORECASE,
)
_ISO_RE = re.compile(
    r"(?:retry(?:-after)?|try again|reset(?:s)?|until)[^\n\r]{0,40}?"
    r"(?P<timestamp>\d{4}-\d{2}-\d{2}[T ][0-9:]{8}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)",
    re.IGNORECASE,
)


def parse_limit_message(
    message: str, *, detected_at: datetime | None = None
) -> LimitDetection | None:
    if not message or not any(pattern.search(message) for pattern in _LIMIT_PATTERNS):
        return None

    now = detected_at or datetime.now(UTC)
    return LimitDetection(
        reason=_summarize_limit_reason(message),
        retry_after=_parse_retry_after(message, now),
    )


def _summarize_limit_reason(message: str) -> str:
    summary = " ".join(message.strip().split())
    if len(summary) > 240:
        return f"{summary[:237]}..."
    return summary


def _parse_retry_after(message: str, detected_at: datetime) -> datetime | None:
    iso_match = _ISO_RE.search(message)
    if iso_match:
        timestamp = iso_match.group("timestamp").replace("Z", "+00:00")
        if "T" not in timestamp:
            timestamp = timestamp.replace(" ", "T", 1)
        parsed = datetime.fromisoformat(timestamp)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)

    duration_match = _DURATION_RE.search(message)
    if not duration_match:
        return None

    amount = int(duration_match.group("amount"))
    unit = duration_match.group("unit").lower()
    if unit.startswith("second"):
        delta = timedelta(seconds=amount)
    elif unit.startswith("minute"):
        delta = timedelta(minutes=amount)
    elif unit.startswith("hour"):
        delta = timedelta(hours=amount)
    else:
        delta = timedelta(days=amount)
    return detected_at + delta


DEFAULT_AVAILABILITY_STORE = AvailabilityStore()
