"""Runs blocking use-cases off the UI thread.

Services are synchronous by design; the GUI must never block on them. Every
call goes through :class:`TaskRunner`, which executes the callable on a worker
thread and delivers the result back through Qt signals - i.e. on the UI thread.
"""

from __future__ import annotations

import traceback
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

from gta_mod_manager.core.logging_setup import get_logger

_LOGGER = get_logger("gui.workers")


class TaskSignals(QObject):
    """Signals emitted by one background task."""

    finished = Signal(object)
    failed = Signal(str)
    completed = Signal()


class _Task(QRunnable):
    """A callable executed on the global thread pool."""

    def __init__(self, work: Callable[[], Any]) -> None:
        super().__init__()
        self._work = work
        self.signals = TaskSignals()

    @Slot()
    def run(self) -> None:
        """Execute the callable and emit the outcome."""
        try:
            result = self._work()
        except Exception as error:  # noqa: BLE001 - reported to the UI
            _LOGGER.error("Background task failed: %s\n%s", error, traceback.format_exc())
            self.signals.failed.emit(str(error))
        else:
            self.signals.finished.emit(result)
        finally:
            self.signals.completed.emit()


class TaskRunner(QObject):
    """Submits work to a thread pool and reports busy state.

    Attributes:
        busyChanged: Emitted with ``True`` when the first task starts and
            ``False`` when the last one finishes.
    """

    busyChanged = Signal(bool)

    def __init__(self, parent: QObject | None = None, max_threads: int = 4) -> None:
        super().__init__(parent)
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(max_threads)
        self._active = 0
        # The thread pool deletes a QRunnable as soon as it returns, so the
        # runner has to keep its signal object alive until the queued
        # deliveries have been processed on the UI thread.
        self._pending: set[TaskSignals] = set()

    @property
    def is_busy(self) -> bool:
        """Return whether at least one task is running."""
        return self._active > 0

    def submit(
        self,
        work: Callable[[], Any],
        on_success: Callable[[Any], None] | None = None,
        on_error: Callable[[str], None] | None = None,
    ) -> None:
        """Run ``work`` in the background.

        Args:
            work: Callable executed off the UI thread.
            on_success: Called on the UI thread with the return value.
            on_error: Called on the UI thread with the error message.
        """
        task = _Task(work)
        signals = task.signals
        self._pending.add(signals)
        if on_success is not None:
            signals.finished.connect(on_success)
        if on_error is not None:
            signals.failed.connect(on_error)
        signals.completed.connect(lambda: self._task_completed(signals))

        self._active += 1
        if self._active == 1:
            self.busyChanged.emit(True)
        self._pool.start(task)

    def wait(self, timeout_ms: int = 30000) -> bool:
        """Block until every task finished; used by tests and shutdown."""
        return self._pool.waitForDone(timeout_ms)

    def _task_completed(self, signals: TaskSignals) -> None:
        """Release the finished task and update the busy state."""
        self._pending.discard(signals)
        self._active = max(0, self._active - 1)
        if self._active == 0:
            self.busyChanged.emit(False)
