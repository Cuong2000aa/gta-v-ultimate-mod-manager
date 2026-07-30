"""View model for the game diagnostics page."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from gta_mod_manager.gui.i18n import t
from gta_mod_manager.gui.viewmodels.base import ViewModel
from gta_mod_manager.gui.workers import TaskRunner
from gta_mod_manager.models.diagnostic import DiagnosticFinding, DiagnosticReport
from gta_mod_manager.services.diagnostics_service import DiagnosticsService
from gta_mod_manager.services.game_service import GameService


class DiagnosticsViewModel(ViewModel):
    """Runs the diagnostics scanner and exposes the report.

    Attributes:
        reportLoaded: Emitted with a :class:`DiagnosticReport` or ``None``.
        fixApplied: Emitted with a short success message after a repair.
    """

    reportLoaded = Signal(object)
    fixApplied = Signal(str)

    def __init__(
        self,
        runner: TaskRunner,
        diagnostics: DiagnosticsService,
        game: GameService,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(runner, parent)
        self._diagnostics = diagnostics
        self._game = game
        self._report: DiagnosticReport | None = None

    @property
    def report(self) -> DiagnosticReport | None:
        """Return the last loaded report, if any."""
        return self._report

    def refresh(self) -> None:
        """Re-run diagnostics in the background."""
        if self._game.active is None:
            resolved = self._game.resolve_active()
            if resolved.is_error:
                self._report = None
                self.reportLoaded.emit(None)
                self.statusChanged.emit(t("diagnostics.need_game"))
                return

        self.statusChanged.emit(t("diagnostics.scanning"))

        def work() -> DiagnosticReport | None:
            return self._diagnostics.run()

        self.run(work, self._publish)

    def repair(self, finding: DiagnosticFinding) -> None:
        """Apply the one-click fix for ``finding`` after the view confirmed."""
        if not finding.is_fixable:
            self.errorRaised.emit(t("diagnostics.fix_unavailable"))
            return

        action = finding.fix_action
        targets = finding.fix_targets
        self.statusChanged.emit(t("diagnostics.fixing"))

        def work():
            return self._diagnostics.apply_fix(action, targets)

        self.run_result(work, self._on_fix_done)

    def _on_fix_done(self, message: str) -> None:
        """Notify the UI and re-scan after a successful repair."""
        self.fixApplied.emit(message)
        self.statusChanged.emit(message)
        self.refresh()

    def _publish(self, report: DiagnosticReport | None) -> None:
        """Emit the report and a short status line."""
        self._report = report
        self.reportLoaded.emit(report)
        if report is None:
            self.statusChanged.emit(t("diagnostics.need_game"))
            return
        if report.problem_count == 0:
            self.statusChanged.emit(t("diagnostics.clean"))
        else:
            self.statusChanged.emit(
                t(
                    "diagnostics.summary_status",
                    errors=report.error_count,
                    warnings=report.warning_count,
                )
            )
