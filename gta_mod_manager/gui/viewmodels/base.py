"""Base class shared by every view model."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, Signal

from gta_mod_manager.core.result import Result
from gta_mod_manager.gui.workers import TaskRunner


class ViewModel(QObject):
    """Common plumbing for view models.

    A view model exposes state through signals and commands through methods.
    It never imports a widget, which is what lets the whole presentation logic
    be tested without showing a window.

    Attributes:
        busyChanged: Emitted when a background command starts or ends.
        errorRaised: Emitted with a user-facing message when a command fails.
        statusChanged: Emitted with a short status line for the UI.
    """

    busyChanged = Signal(bool)
    errorRaised = Signal(str)
    statusChanged = Signal(str)

    def __init__(self, runner: TaskRunner, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._runner = runner
        self._runner.busyChanged.connect(self.busyChanged)

    @property
    def runner(self) -> TaskRunner:
        """Return the shared task runner."""
        return self._runner

    def run(
        self,
        work: Callable[[], Any],
        on_success: Callable[[Any], None] | None = None,
        on_error: Callable[[str], None] | None = None,
    ) -> None:
        """Execute ``work`` in the background, reporting errors by default."""
        self._runner.submit(work, on_success, on_error or self._emit_error)

    def run_result(
        self,
        work: Callable[[], Result[Any]],
        on_value: Callable[[Any], None],
        *,
        on_warnings: Callable[[tuple[str, ...]], None] | None = None,
    ) -> None:
        """Execute a command returning :class:`Result` and unwrap it safely.

        Expected failures (``Result.error``) become :attr:`errorRaised`
        signals; unexpected exceptions do too, so the UI has one error path.
        """

        def handle(result: Result[Any]) -> None:
            if result.is_error:
                self._emit_error(result.error or "The operation failed")
                return
            if result.warnings and on_warnings is not None:
                on_warnings(result.warnings)
            on_value(result.value)

        self._runner.submit(work, handle, self._emit_error)

    def _emit_error(self, message: str) -> None:
        """Emit :attr:`errorRaised` with ``message``."""
        self.errorRaised.emit(message)
