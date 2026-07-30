"""View model driving the scan / analyse / preview / install workflow."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from gta_mod_manager.core.app_paths import AppPaths
from gta_mod_manager.core.progress import EventBusProgressReporter
from gta_mod_manager.core.result import Result
from gta_mod_manager.gui.viewmodels.base import ViewModel
from gta_mod_manager.gui.workers import TaskRunner
from gta_mod_manager.models.mod_package import ModPackage
from gta_mod_manager.models.variant_selection import VariantSelection
from gta_mod_manager.scanner.workspace import TempWorkspace
from gta_mod_manager.services.analysis_service import AnalysisService
from gta_mod_manager.services.game_service import GameService
from gta_mod_manager.services.install_service import InstallPreview, InstallReport, InstallService
from gta_mod_manager.services.online_mod_service import delete_owned_download


@dataclass(frozen=True, slots=True)
class PreviewRow:
    """One line of the preview table."""

    action: str
    zone: str
    target: str
    detail: str


class InstallViewModel(ViewModel):
    """Owns the state of one pending installation.

    The workspace holding the extracted files stays alive between *analyse* and
    *install* and is disposed of when the user confirms, cancels or drops
    another package.

    Attributes:
        previewReady: Emitted with an :class:`InstallPreview`.
        installFinished: Emitted with an :class:`InstallReport`.
        cleared: Emitted when the pending package was discarded.
    """

    previewReady = Signal(object)
    installFinished = Signal(object)
    cleared = Signal()

    def __init__(
        self,
        runner: TaskRunner,
        analysis: AnalysisService,
        installer: InstallService,
        game: GameService,
        reporter: EventBusProgressReporter,
        parent: QObject | None = None,
        *,
        paths: AppPaths | None = None,
    ) -> None:
        super().__init__(runner, parent)
        self._analysis = analysis
        self._installer = installer
        self._game = game
        self._reporter = reporter
        self._paths = paths
        self._workspace: TempWorkspace | None = None
        self._preview: InstallPreview | None = None

    @property
    def preview(self) -> InstallPreview | None:
        """Return the pending preview, if a package was analysed."""
        return self._preview

    def analyze(self, source: Path) -> None:
        """Scan and analyse ``source``, then build and evaluate the plan."""
        game = self._game.active
        if game is None:
            resolved = self._game.resolve_active()
            if resolved.is_error:
                self.errorRaised.emit(
                    "Select a valid GTA V installation before importing mods"
                )
                return
            game = resolved.unwrap()

        self.clear()
        self.statusChanged.emit(f"Analyzing {source.name}...")

        def work() -> Result[InstallPreview]:
            workspace = self._analysis.create_workspace()
            self._workspace = workspace
            analysed = self._analysis.analyze(source, workspace, reporter=self._reporter)
            if analysed.is_error:
                return Result.fail(analysed.error or "Analysis failed", code=analysed.code)
            package: ModPackage = analysed.unwrap()
            status = self._game.status(game)
            components = status.unwrap().components if status.is_ok else None
            return self._installer.preview(package, game, components)

        self.run_result(work, self._on_preview, on_warnings=self._on_warnings)

    def set_variants(self, *, addon: bool, replace: bool) -> None:
        """Rebuild the plan for the pending package with a new variant choice."""
        preview = self._preview
        if preview is None:
            return
        selection = VariantSelection(addon=addon, replace=replace)
        if selection == preview.variants:
            return
        self.statusChanged.emit("Updating install plan...")

        def work() -> Result[InstallPreview]:
            status = self._game.status(preview.install)
            components = status.unwrap().components if status.is_ok else None
            return self._installer.preview(
                preview.package,
                preview.install,
                components,
                variants=selection,
            )

        self.run_result(work, self._on_preview, on_warnings=self._on_warnings)

    def confirm(self) -> None:
        """Install the pending preview."""
        preview = self._preview
        if preview is None:
            self.errorRaised.emit("There is nothing to install")
            return
        if not preview.is_installable:
            self.errorRaised.emit("\n".join(preview.blocking_reasons))
            return

        self.statusChanged.emit(f"Installing {preview.plan.display_name}...")

        def work() -> Result[InstallReport]:
            return self._installer.install(preview, reporter=self._reporter)

        self.run_result(work, self._on_installed)

    def clear(self) -> None:
        """Discard the pending package and delete its workspace."""
        if self._workspace is not None:
            self._workspace.dispose()
            self._workspace = None
        self._preview = None
        self.cleared.emit()

    def preview_rows(self) -> tuple[PreviewRow, ...]:
        """Return the pending plan as table rows."""
        if self._preview is None:
            return ()
        game_root = self._preview.install.root_path
        rows: list[PreviewRow] = []
        for operation in self._preview.plan.operations:
            target = operation.target_path
            try:
                shown = str(target.relative_to(game_root))
            except ValueError:
                shown = str(target)
            rows.append(
                PreviewRow(
                    action=operation.action.value.replace("_", " "),
                    zone=operation.target_kind.value,
                    target=shown,
                    detail=operation.description,
                )
            )
        return tuple(rows)

    def _on_preview(self, preview: InstallPreview) -> None:
        """Store and publish the freshly built preview."""
        self._preview = preview
        self.previewReady.emit(preview)
        classification = preview.package.classification
        self.statusChanged.emit(
            f"{preview.package.display_name}: {classification.primary.display_name} "
            f"({classification.score:.0%} confidence), "
            f"{len(preview.plan.operations)} operation(s)"
        )

    def _on_installed(self, report: InstallReport) -> None:
        """Publish the install report and release the workspace."""
        source = self._preview.package.source_path if self._preview is not None else None
        self.installFinished.emit(report)
        self.statusChanged.emit(
            f"{report.mod.display_name} installed ({report.file_count} file(s))"
        )
        self.clear()
        self._delete_online_download(source)

    def _delete_online_download(self, source: Path | None) -> None:
        """Remove archives fetched into the app downloads folder after install."""
        if source is None or self._paths is None:
            return
        delete_owned_download(source, self._paths.downloads)

    def _on_warnings(self, warnings: tuple[str, ...]) -> None:
        """Surface non-fatal analysis warnings in the status line."""
        if warnings:
            self.statusChanged.emit(" | ".join(warnings))
