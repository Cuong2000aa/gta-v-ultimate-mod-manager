"""Default :class:`~gta_mod_manager.core.protocols.ProgressReporter` adapters."""

from __future__ import annotations

from gta_mod_manager.core.events import EventBus, ProgressEvent


class NullProgressReporter:
    """A reporter that discards everything; used in tests and headless code."""

    def start(self, operation_id: str, label: str, total: int = 0) -> None:
        """Ignore the start of an operation."""

    def advance(self, operation_id: str, current: int, label: str | None = None) -> None:
        """Ignore progress updates."""

    def finish(self, operation_id: str, label: str | None = None) -> None:
        """Ignore the end of an operation."""


class EventBusProgressReporter:
    """Publishes :class:`ProgressEvent` instances on the application bus."""

    def __init__(self, bus: EventBus) -> None:
        self._bus = bus
        self._totals: dict[str, int] = {}
        self._labels: dict[str, str] = {}

    def start(self, operation_id: str, label: str, total: int = 0) -> None:
        """Publish the initial event and remember the total work amount."""
        self._totals[operation_id] = total
        self._labels[operation_id] = label
        self._bus.publish(ProgressEvent(operation_id=operation_id, label=label, total=total))

    def advance(self, operation_id: str, current: int, label: str | None = None) -> None:
        """Publish an intermediate progress event."""
        resolved = label or self._labels.get(operation_id, "")
        self._bus.publish(
            ProgressEvent(
                operation_id=operation_id,
                label=resolved,
                current=current,
                total=self._totals.get(operation_id, 0),
            )
        )

    def finish(self, operation_id: str, label: str | None = None) -> None:
        """Publish a completion event and forget the operation."""
        total = self._totals.pop(operation_id, 0)
        resolved = label or self._labels.pop(operation_id, "")
        self._bus.publish(
            ProgressEvent(
                operation_id=operation_id, label=resolved, current=total, total=total
            )
        )
