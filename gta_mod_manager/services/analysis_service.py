"""Use-case: turn a dropped file into a fully analysed :class:`ModPackage`."""

from __future__ import annotations

from pathlib import Path

from gta_mod_manager.analyzer.dependency_resolver import DependencyResolver
from gta_mod_manager.analyzer.engine import ModAnalyzer
from gta_mod_manager.core.app_paths import AppPaths
from gta_mod_manager.core.exceptions import ScanError
from gta_mod_manager.core.logging_setup import get_logger
from gta_mod_manager.core.protocols import ProgressReporter
from gta_mod_manager.core.result import Result
from gta_mod_manager.models.component import ComponentReport
from gta_mod_manager.models.mod_file import FileInventory
from gta_mod_manager.models.mod_package import DependencyRef, ModPackage, ReadmeExcerpt
from gta_mod_manager.repository.settings_repository import JsonSettingsRepository
from gta_mod_manager.scanner.package_scanner import PackageScanner
from gta_mod_manager.scanner.workspace import TempWorkspace
from gta_mod_manager.utils import hashing, xml_tools
from gta_mod_manager.validator.xml_validator import XmlValidator

_LOGGER = get_logger("services.analysis")

#: How much of a readme is kept for the preview dialog.
_README_PREVIEW_CHARS = 4000

#: How many documentation excerpts the preview dialog shows.
_README_PREVIEW_LIMIT = 6

#: File-name fragments that mark an instruction / readme document.
_DOC_NAME_HINTS: tuple[str, ...] = (
    "readme",
    "read me",
    "read_me",
    "instruction",
    "instalation",
    "installation",
    "install",
    "how to",
    "howto",
    "spawn",
    "info",
    "说明",
)


class AnalysisService:
    """Scans, repairs and classifies a mod package.

    The workspace is *not* disposed by this service: the returned package
    points into it and the installer still needs those files. Callers own the
    workspace and dispose of it when the installation finished or was aborted.
    """

    def __init__(
        self,
        scanner: PackageScanner,
        analyzer: ModAnalyzer,
        resolver: DependencyResolver,
        xml_validator: XmlValidator,
        paths: AppPaths,
        settings: JsonSettingsRepository,
    ) -> None:
        self._scanner = scanner
        self._analyzer = analyzer
        self._resolver = resolver
        self._xml_validator = xml_validator
        self._paths = paths
        self._settings = settings

    def create_workspace(self) -> TempWorkspace:
        """Return a fresh extraction workspace honouring the user's settings."""
        return TempWorkspace(self._paths, keep=self._settings.load().keep_extracted_temp)

    def analyze(
        self,
        source: Path,
        workspace: TempWorkspace,
        *,
        repair_xml: bool = True,
        reporter: ProgressReporter | None = None,
    ) -> Result[ModPackage]:
        """Scan and classify ``source`` inside ``workspace``.

        Args:
            source: Archive, folder or loose file dropped by the user.
            workspace: Extraction workspace owned by the caller.
            repair_xml: Repair malformed meta files inside the workspace.
            reporter: Optional progress sink.
        """
        try:
            inventory = self._scanner.scan(source, workspace.root, reporter)
        except ScanError as error:
            return Result.fail(str(error), code="analysis.scan_failed")

        if inventory.count == 0:
            return Result.fail(
                "The package contains no files after extraction", code="analysis.empty"
            )

        warnings: list[str] = []
        if repair_xml:
            repaired = self._xml_validator.repair_in_place(inventory)
            if repaired:
                warnings.append(f"Repaired {len(repaired)} malformed XML file(s)")

        xml_report = self._xml_validator.validate(inventory)
        if xml_report.broken:
            warnings.append(
                f"{len(xml_report.broken)} XML file(s) are unreadable and will be skipped"
            )

        analysis = self._analyzer.analyze_detailed(inventory, source_name=source.name)
        package = ModPackage(
            package_id=self._package_id(source),
            display_name=self._display_name(source),
            source_path=source,
            extracted_root=inventory.root,
            inventory=inventory,
            classification=analysis.classification,
            dependencies=self._resolver.resolve(analysis.classification),
            readmes=self._collect_readmes(inventory),
            preview_image=self._pick_preview(inventory),
        )

        self._settings.save(self._settings.load().with_recent_source(source))
        _LOGGER.info(
            "Prepared package %s (%s, %.0f%% confidence)",
            package.display_name,
            package.classification.primary.value,
            package.classification.score * 100,
        )
        return Result(value=package, warnings=tuple(warnings))

    def unmet_dependencies(
        self, package: ModPackage, components: ComponentReport
    ) -> tuple[DependencyRef, ...]:
        """Return the dependencies of ``package`` that are not installed."""
        return self._resolver.unmet(package.dependencies, components)

    @staticmethod
    def _package_id(source: Path) -> str:
        """Return a stable identifier derived from the source path and name."""
        return hashing.short_id(f"{source.name}|{source.stat().st_size if source.is_file() else 0}")

    @staticmethod
    def _display_name(source: Path) -> str:
        """Return a readable mod name derived from the source file name."""
        return source.stem if source.is_file() else source.name

    @staticmethod
    def _collect_readmes(inventory: FileInventory) -> tuple[ReadmeExcerpt, ...]:
        """Return readable excerpts of the documentation shipped in a package."""
        candidates = [
            file
            for file in inventory.files
            if file.suffix in {".txt", ".md", ".nfo"}
            and any(hint in Path(file.lower_name).stem for hint in _DOC_NAME_HINTS)
        ]
        candidates.sort(
            key=lambda item: (
                0 if "spawn" in item.lower_name else 1,
                0 if "readme" in item.lower_name else 1,
                len(item.relative_path.parts),
                item.lower_name,
            )
        )
        excerpts: list[ReadmeExcerpt] = []
        for file in candidates[:_README_PREVIEW_LIMIT]:
            try:
                text = xml_tools.read_text(file.absolute_path)[:_README_PREVIEW_CHARS]
            except OSError:
                continue
            if text.strip():
                excerpts.append(ReadmeExcerpt(source=file.absolute_path, text=text.strip()))
        return tuple(excerpts)

    @staticmethod
    def _pick_preview(inventory: FileInventory) -> Path | None:
        """Return the best preview image inside the package, if there is one."""
        images = inventory.preview_images()
        return images[0].absolute_path if images else None
