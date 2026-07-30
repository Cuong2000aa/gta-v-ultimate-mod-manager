"""Detects installed third-party components and missing dependencies."""

from __future__ import annotations

from pathlib import Path

from gta_mod_manager.core.logging_setup import get_logger
from gta_mod_manager.detector.component_catalog import ComponentProbe, default_catalog
from gta_mod_manager.models.component import ComponentReport, DetectedComponent
from gta_mod_manager.models.enums import ComponentStatus
from gta_mod_manager.models.game_install import GameInstall
from gta_mod_manager.utils import windows

_LOGGER = get_logger("detector.components")


class ComponentDetector:
    """Reports which components are present inside an installation."""

    def __init__(self, catalog: tuple[ComponentProbe, ...] | None = None) -> None:
        self._catalog = catalog if catalog is not None else default_catalog()

    def detect(self, install: GameInstall) -> ComponentReport:
        """Return the state of every catalogued component for ``install``."""
        detected = tuple(self._probe(probe, install) for probe in self._catalog)
        missing = [item.display_name for item in detected if item.is_missing_dependency]
        if missing:
            _LOGGER.info("Missing essential component(s): %s", ", ".join(missing))
        return ComponentReport(components=detected)

    def _probe(self, probe: ComponentProbe, install: GameInstall) -> DetectedComponent:
        """Evaluate a single probe against the installation."""
        hits = self._collect_hits(probe, install)

        if not hits or (probe.require_all and len(hits) < self._expected_count(probe)):
            return DetectedComponent(
                spec=probe.spec,
                status=ComponentStatus.MISSING,
                details="Not found in the game folder",
            )

        location = hits[0]
        version = self._read_version(probe, install, hits)
        return DetectedComponent(
            spec=probe.spec,
            status=ComponentStatus.INSTALLED,
            version=version,
            location=location,
            details=f"{len(hits)} matching entry(ies)",
        )

    @staticmethod
    def _expected_count(probe: ComponentProbe) -> int:
        """Return how many entries must exist when ``require_all`` is set."""
        return len(probe.root_files) + len(probe.root_directories) + len(probe.mods_files)

    @staticmethod
    def _collect_hits(probe: ComponentProbe, install: GameInstall) -> list[Path]:
        """Return every catalogued path that exists on disk."""
        hits: list[Path] = []
        for relative in probe.root_files:
            candidate = install.root_path.joinpath(*relative.split("/"))
            if candidate.is_file():
                hits.append(candidate)
        for relative in probe.root_directories:
            candidate = install.root_path.joinpath(*relative.split("/"))
            if candidate.is_dir():
                hits.append(candidate)
        for relative in probe.mods_files:
            candidate = install.mods_path.joinpath(*relative.split("/"))
            if candidate.exists():
                hits.append(candidate)
        return hits

    @staticmethod
    def _read_version(
        probe: ComponentProbe, install: GameInstall, hits: list[Path]
    ) -> str | None:
        """Return the component version, when a binary declares one."""
        if probe.version_from:
            candidate = install.root_path.joinpath(*probe.version_from.split("/"))
            if candidate.is_file():
                return windows.read_file_version(candidate)
        for hit in hits:
            if hit.is_file() and hit.suffix.lower() in (".dll", ".asi", ".exe"):
                version = windows.read_file_version(hit)
                if version:
                    return version
        return None
