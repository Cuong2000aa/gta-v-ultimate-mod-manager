"""Bridges the framework-agnostic event bus onto Qt signals.

Application services publish plain dataclasses on the
:class:`~gta_mod_manager.core.events.EventBus` from whichever thread they run
on. The relay re-emits them as Qt signals; because the relay lives on the UI
thread, Qt automatically queues the delivery, so widgets are only ever touched
from the main thread.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from gta_mod_manager.core.events import (
    EventBus,
    GameChangedEvent,
    GameSessionEndedEvent,
    GameSessionStartedEvent,
    LogEvent,
    ModLibraryChangedEvent,
    NotificationEvent,
    ProgressEvent,
)


class EventRelay(QObject):
    """Re-emits application events as Qt signals.

    Attributes:
        progress: ``(operation_id, label, current, total)``.
        notified: ``(title, message, level)``.
        logged: ``(level, logger, message)``.
        gameChanged: ``(game_id, root_path)``.
        libraryChanged: ``(reason,)``.
        sessionStarted: ``(process_name, pid)``.
        sessionEnded: ``(report,)`` — a ``GameSessionReport``.
    """

    progress = Signal(str, str, int, int)
    notified = Signal(str, str, str)
    logged = Signal(str, str, str)
    gameChanged = Signal(str, str)
    libraryChanged = Signal(str)
    sessionStarted = Signal(str, int)
    sessionEnded = Signal(object)

    def __init__(self, bus: EventBus, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._bus = bus
        self._unsubscribers = [
            bus.subscribe(ProgressEvent, self._on_progress),
            bus.subscribe(NotificationEvent, self._on_notification),
            bus.subscribe(LogEvent, self._on_log),
            bus.subscribe(GameChangedEvent, self._on_game_changed),
            bus.subscribe(ModLibraryChangedEvent, self._on_library_changed),
            bus.subscribe(GameSessionStartedEvent, self._on_session_started),
            bus.subscribe(GameSessionEndedEvent, self._on_session_ended),
        ]

    def detach(self) -> None:
        """Unsubscribe from the bus; called when the window closes."""
        for unsubscribe in self._unsubscribers:
            unsubscribe()
        self._unsubscribers.clear()

    def _on_progress(self, event: ProgressEvent) -> None:
        """Forward a progress event."""
        self.progress.emit(event.operation_id, event.label, event.current, event.total)

    def _on_notification(self, event: NotificationEvent) -> None:
        """Forward a toast notification."""
        self.notified.emit(event.title, event.message, event.level.value)

    def _on_log(self, event: LogEvent) -> None:
        """Forward a log record."""
        self.logged.emit(event.level, event.logger, event.message)

    def _on_game_changed(self, event: GameChangedEvent) -> None:
        """Forward the active-installation change."""
        self.gameChanged.emit(event.game_id, event.root_path)

    def _on_library_changed(self, event: ModLibraryChangedEvent) -> None:
        """Forward a library change."""
        self.libraryChanged.emit(event.reason)

    def _on_session_started(self, event: GameSessionStartedEvent) -> None:
        """Forward the start of a monitored game session."""
        self.sessionStarted.emit(event.process_name, event.pid)

    def _on_session_ended(self, event: GameSessionEndedEvent) -> None:
        """Forward the report of a finished game session."""
        self.sessionEnded.emit(event.report)
