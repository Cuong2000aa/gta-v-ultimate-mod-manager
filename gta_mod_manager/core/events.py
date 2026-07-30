"""A tiny, thread-safe publish/subscribe bus.

The application layer emits progress and notification events without knowing
anything about Qt. The GUI subscribes and marshals them onto the UI thread.
"""

from __future__ import annotations

import threading
import uuid
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, TypeVar


class NotificationLevel(str, Enum):
    """Severity used by toast notifications."""

    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True)
class AppEvent:
    """Base class for everything published on the bus."""

    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc), kw_only=True
    )


@dataclass(frozen=True)
class ProgressEvent(AppEvent):
    """Reports progress of a long running operation.

    Attributes:
        operation_id: Correlates every event of the same operation.
        label: Short description shown next to the progress bar.
        current: Completed work units.
        total: Total work units, or ``0`` when indeterminate.
    """

    operation_id: str
    label: str
    current: int = 0
    total: int = 0

    @property
    def percent(self) -> int:
        """Return completion in percent, or ``0`` when indeterminate."""
        if self.total <= 0:
            return 0
        return min(100, int(self.current * 100 / self.total))


@dataclass(frozen=True)
class NotificationEvent(AppEvent):
    """A user facing toast message."""

    title: str
    message: str
    level: NotificationLevel = NotificationLevel.INFO


@dataclass(frozen=True)
class LogEvent(AppEvent):
    """A log record mirrored into the in-app log viewer."""

    level: str
    logger: str
    message: str


@dataclass(frozen=True)
class GameChangedEvent(AppEvent):
    """Published when the active game installation changes."""

    game_id: str
    root_path: str


@dataclass(frozen=True)
class ModLibraryChangedEvent(AppEvent):
    """Published when installed mods were added, removed or updated."""

    reason: str = "changed"


@dataclass(frozen=True)
class GameSessionStartedEvent(AppEvent):
    """Published when the crash monitor sees the game process appear."""

    process_name: str
    pid: int


@dataclass(frozen=True)
class GameSessionEndedEvent(AppEvent):
    """Published when the watched game process exits.

    Attributes:
        report: A :class:`~gta_mod_manager.models.crash_report.GameSessionReport`.
            Typed as ``object`` to keep the event module free of model imports.
    """

    report: object


TEvent = TypeVar("TEvent", bound=AppEvent)
Subscriber = Callable[[Any], None]


class EventBus:
    """Synchronous, thread-safe event dispatcher."""

    def __init__(self) -> None:
        self._subscribers: dict[type[AppEvent], list[Subscriber]] = defaultdict(list)
        self._lock = threading.RLock()

    def subscribe(
        self, event_type: type[TEvent], handler: Callable[[TEvent], None]
    ) -> Callable[[], None]:
        """Register ``handler`` for ``event_type``.

        Returns:
            A callable that removes the subscription again.
        """
        with self._lock:
            self._subscribers[event_type].append(handler)  # type: ignore[arg-type]

        def unsubscribe() -> None:
            with self._lock:
                handlers = self._subscribers.get(event_type, [])
                if handler in handlers:  # type: ignore[comparison-overlap]
                    handlers.remove(handler)  # type: ignore[arg-type]

        return unsubscribe

    def publish(self, event: AppEvent) -> None:
        """Deliver ``event`` to every handler registered for its exact type.

        Handler exceptions are swallowed so one broken subscriber can never
        abort an installation.
        """
        with self._lock:
            handlers = list(self._subscribers.get(type(event), ()))
        for handler in handlers:
            try:
                handler(event)
            except Exception:  # noqa: BLE001 - subscribers must not break producers
                continue

    def clear(self) -> None:
        """Remove every subscription (used by tests)."""
        with self._lock:
            self._subscribers.clear()


def new_operation_id() -> str:
    """Return a short unique identifier for correlating operation events."""
    return uuid.uuid4().hex[:12]
