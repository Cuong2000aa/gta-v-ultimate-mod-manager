"""View model for the log viewer."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from gta_mod_manager.core.logging_setup import LogRecordView, RingBufferHandler
from gta_mod_manager.gui.viewmodels.base import ViewModel
from gta_mod_manager.gui.workers import TaskRunner

LOG_LEVELS: tuple[str, ...] = ("ALL", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")

_LEVEL_ORDER = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40, "CRITICAL": 50}


class LogViewModel(ViewModel):
    """Exposes the in-memory log buffer with level and text filtering.

    Attributes:
        recordsLoaded: Emitted with a tuple of :class:`LogRecordView`.
    """

    recordsLoaded = Signal(object)

    def __init__(
        self,
        runner: TaskRunner,
        buffer: RingBufferHandler,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(runner, parent)
        self._buffer = buffer
        self._min_level = "ALL"
        self._query = ""

    def set_level(self, level: str) -> None:
        """Filter out records below ``level``."""
        self._min_level = level
        self.refresh()

    def search(self, query: str) -> None:
        """Filter records by substring."""
        self._query = query.strip().lower()
        self.refresh()

    def refresh(self) -> None:
        """Re-read and re-filter the buffer."""
        self.recordsLoaded.emit(self._filtered())

    def clear(self) -> None:
        """Drop every buffered record."""
        self._buffer.clear()
        self.refresh()

    def _filtered(self) -> tuple[LogRecordView, ...]:
        """Return the records matching the active filters."""
        threshold = _LEVEL_ORDER.get(self._min_level, 0)
        records = []
        for record in self._buffer.records():
            if _LEVEL_ORDER.get(record.level, 0) < threshold:
                continue
            if self._query and self._query not in record.message.lower():
                continue
            records.append(record)
        return tuple(records)
