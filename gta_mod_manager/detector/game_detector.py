"""Aggregates every detection source into one validated result set."""

from __future__ import annotations

from pathlib import Path

from gta_mod_manager.core import constants
from gta_mod_manager.core.exceptions import InvalidGameInstallationError
from gta_mod_manager.core.logging_setup import get_logger
from gta_mod_manager.detector.sources import DetectionSource, default_sources
from gta_mod_manager.models.enums import GamePlatform
from gta_mod_manager.models.game_install import GameInstall, ValidationIssue, ValidationReport
from gta_mod_manager.utils import fs, windows

_LOGGER = get_logger("detector.game")

#: Platform hints derived from the installation path itself.
_PATH_PLATFORM_HINTS: tuple[tuple[str, GamePlatform], ...] = (
    ("steamapps", GamePlatform.STEAM),
    ("epic games", GamePlatform.EPIC),
    ("rockstar games", GamePlatform.ROCKSTAR),
)


class GameDetector:
    """Finds and validates GTA V installations.

    The detector owns no knowledge of *where* to look; that lives in the
    injected sources, which makes adding a new launcher a one-file change.
    """

    def __init__(self, sources: tuple[DetectionSource, ...] | None = None) -> None:
        self._sources = sources if sources is not None else default_sources()

    def detect_all(self) -> tuple[GameInstall, ...]:
        """Return every valid installation, best candidate first.

        Duplicates reported by multiple sources are merged; the entry with the
        most specific platform wins.
        """
        discovered: dict[str, GameInstall] = {}
        for source in self._sources:
            for candidate in self._safe_candidates(source):
                install = self._accept(source, candidate)
                if install is None:
                    continue
                key = str(install.root_path).lower()
                existing = discovered.get(key)
                if existing is None or self._is_better(install, existing):
                    discovered[key] = install
        results = tuple(discovered.values())
        _LOGGER.info("Detected %d GTA V installation(s)", len(results))
        return results

    def detect_primary(self) -> GameInstall | None:
        """Return the most likely installation, or ``None`` when none exists."""
        installs = self.detect_all()
        return installs[0] if installs else None

    def from_path(self, root: Path) -> GameInstall:
        """Build an installation from a folder the user selected manually.

        Raises:
            InvalidGameInstallationError: When ``root`` is not a GTA V folder.
        """
        report = self.validate(root)
        if not report.is_valid:
            raise InvalidGameInstallationError(
                "The selected folder is not a valid GTA V installation",
                path=str(root),
                issues=[issue.message for issue in report.fatal_issues],
            )
        normalised = fs.normalise(root)
        executable = normalised / constants.PRIMARY_EXECUTABLE
        install = GameInstall(
            game_id=constants.GAME_ID_GTA_V,
            root_path=normalised,
            platform=self._guess_platform(normalised),
            executable=executable if executable.is_file() else None,
            detected_by="manual",
        )
        return install.with_version(self._read_version(install))

    def validate(self, root: Path) -> ValidationReport:
        """Check whether ``root`` looks like a real GTA V installation."""
        issues: list[ValidationIssue] = []
        normalised = fs.normalise(root)

        if not normalised.is_dir():
            return ValidationReport(
                issues=(
                    ValidationIssue(
                        code="game.missing_folder",
                        message="The folder does not exist",
                        is_fatal=True,
                        path=normalised,
                    ),
                )
            )

        executable = normalised / constants.PRIMARY_EXECUTABLE
        if not executable.is_file():
            issues.append(
                ValidationIssue(
                    code="game.missing_executable",
                    message=f"{constants.PRIMARY_EXECUTABLE} was not found in this folder",
                    is_fatal=True,
                    path=executable,
                )
            )

        missing_signatures = [
            entry
            for entry in constants.GAME_SIGNATURE_ENTRIES
            if not (normalised / entry).exists()
        ]
        if len(missing_signatures) > 2:
            issues.append(
                ValidationIssue(
                    code="game.incomplete_layout",
                    message="Typical GTA V files are missing: "
                    + ", ".join(missing_signatures),
                    is_fatal=True,
                    path=normalised,
                )
            )
        elif missing_signatures:
            issues.append(
                ValidationIssue(
                    code="game.partial_layout",
                    message="Some expected entries are missing: "
                    + ", ".join(missing_signatures),
                    path=normalised,
                )
            )

        if not self._is_writable(normalised):
            issues.append(
                ValidationIssue(
                    code="game.not_writable",
                    message="The game folder is not writable; run the manager as "
                    "administrator or move the game out of Program Files",
                    is_fatal=True,
                    path=normalised,
                )
            )

        if not (normalised / constants.MODS_FOLDER_NAME).is_dir():
            issues.append(
                ValidationIssue(
                    code="game.no_mods_folder",
                    message="No 'mods' folder yet; it will be created on first install",
                    path=normalised / constants.MODS_FOLDER_NAME,
                )
            )

        return ValidationReport(issues=tuple(issues))

    def _safe_candidates(self, source: DetectionSource) -> tuple[Path, ...]:
        """Return the candidates of ``source``, tolerating source failures."""
        try:
            return source.candidate_paths()
        except Exception as error:  # noqa: BLE001 - one broken source must not stop detection
            _LOGGER.warning("Detection source %s failed: %s", source.source_name, error)
            return ()

    def _accept(self, source: DetectionSource, candidate: Path) -> GameInstall | None:
        """Validate ``candidate`` and turn it into an installation entity."""
        if not candidate.is_dir():
            return None
        if not self.validate(candidate).is_valid:
            return None
        install = source.build_install(candidate)
        if install.platform is GamePlatform.UNKNOWN:
            install = GameInstall(
                game_id=install.game_id,
                root_path=install.root_path,
                platform=self._guess_platform(install.root_path),
                executable=install.executable,
                detected_by=install.detected_by,
            )
        return install.with_version(self._read_version(install))

    @staticmethod
    def _read_version(install: GameInstall) -> str | None:
        """Return the version of the game executable, when readable."""
        if install.executable is None:
            return None
        return windows.read_file_version(install.executable)

    @staticmethod
    def _guess_platform(root: Path) -> GamePlatform:
        """Infer the platform from the installation path."""
        lowered = str(root).lower()
        for token, platform in _PATH_PLATFORM_HINTS:
            if token in lowered:
                return platform
        return GamePlatform.MANUAL

    @staticmethod
    def _is_better(candidate: GameInstall, existing: GameInstall) -> bool:
        """Return whether ``candidate`` is a more informative duplicate.

        ``UNKNOWN`` and ``MANUAL`` are both low-confidence platforms: the first
        means the source did not know, the second that it was guessed from the
        path. A source stating an actual launcher always wins over them.
        """
        guessed = (GamePlatform.UNKNOWN, GamePlatform.MANUAL)
        if existing.platform in guessed and candidate.platform not in guessed:
            return True
        if candidate.platform in guessed and existing.platform not in guessed:
            return False
        return existing.version is None and candidate.version is not None

    @staticmethod
    def _is_writable(root: Path) -> bool:
        """Return whether the application may create files inside ``root``."""
        probe = root / ".gmm_write_test"
        try:
            probe.touch(exist_ok=True)
            probe.unlink(missing_ok=True)
        except OSError:
            return False
        return True
