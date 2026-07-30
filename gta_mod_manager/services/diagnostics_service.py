"""Use-case: diagnose common GTA V launch / graphics failures."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

from gta_mod_manager.core.logging_setup import get_logger
from gta_mod_manager.core.result import Result
from gta_mod_manager.diagnostics.repairs import apply_diagnostic_fix
from gta_mod_manager.diagnostics.scanner import DiagnosticsScanner
from gta_mod_manager.models.diagnostic import DiagnosticFinding, DiagnosticReport
from gta_mod_manager.models.game_install import GameInstall
from gta_mod_manager.repository.mod_repository import JsonModRepository
from gta_mod_manager.services.game_service import GameService

_LOGGER = get_logger("services.diagnostics")

#: Supplies the findings of the most recent monitored game session.
SessionFindingsProvider = Callable[[], Sequence[DiagnosticFinding]]


class DiagnosticsService:
    """Runs the diagnostics scanner against the active installation."""

    def __init__(
        self,
        game: GameService,
        scanner: DiagnosticsScanner | None = None,
        mods: JsonModRepository | None = None,
        session_findings: SessionFindingsProvider | None = None,
    ) -> None:
        self._game = game
        self._scanner = scanner or DiagnosticsScanner()
        self._mods = mods
        self._session_findings = session_findings

    def run(self, install: GameInstall | None = None) -> DiagnosticReport | None:
        """Scan ``install`` (or the active one) and return the report."""
        target = install or self._game.active
        if target is None:
            resolved = self._game.resolve_active()
            if resolved.is_error:
                return None
            target = resolved.unwrap()

        status = self._game.status(target)
        components = status.unwrap().components if status.is_ok else None
        installed = (
            self._mods.list_for_game(target.root_path) if self._mods is not None else ()
        )
        report = self._scanner.scan(target, components, installed)
        report = self._with_session_findings(report)
        _LOGGER.info(
            "Diagnostics complete: %d error(s), %d warning(s)",
            report.error_count,
            report.warning_count,
        )
        return report

    def apply_fix(
        self,
        action: str,
        targets: tuple[str, ...] | list[str],
        install: GameInstall | None = None,
    ) -> Result[str]:
        """Apply a one-click diagnostics repair to the active (or given) install."""
        target = install or self._game.active
        if target is None:
            resolved = self._game.resolve_active()
            if resolved.is_error:
                return Result.fail(
                    resolved.error or "No GTA V installation selected",
                    code="diagnostics.need_game",
                )
            target = resolved.unwrap()
        return apply_diagnostic_fix(Path(target.root_path), action, targets)

    def _with_session_findings(self, report: DiagnosticReport) -> DiagnosticReport:
        """Prepend the latest game-session findings to ``report``."""
        if self._session_findings is None:
            return report
        try:
            extra = tuple(self._session_findings())
        except Exception as error:  # noqa: BLE001 - diagnostics must not break
            _LOGGER.debug("Session findings unavailable: %s", error)
            return report
        if not extra:
            return report
        return DiagnosticReport(
            game_root=report.game_root, findings=extra + report.findings
        )
