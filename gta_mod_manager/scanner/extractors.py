"""Archive extractors.

Each extractor handles one family of formats and implements the
:class:`~gta_mod_manager.core.protocols.ArchiveExtractor` port. All of them
route member paths through :func:`~gta_mod_manager.utils.fs.safe_join`, so a
malicious archive cannot escape the destination folder.
"""

from __future__ import annotations

import shutil
import subprocess
import zipfile
from collections.abc import Callable
from pathlib import Path, PurePosixPath

from gta_mod_manager.core import constants
from gta_mod_manager.core.exceptions import (
    ArchiveExtractionError,
    DependencyMissingError,
    UnsupportedArchiveError,
)
from gta_mod_manager.core.logging_setup import get_logger
from gta_mod_manager.utils import fs

_LOGGER = get_logger("scanner.extractors")


class ZipExtractor:
    """Handles ``.zip`` archives and ``.oiv`` packages (which are zip files)."""

    @property
    def supported_suffixes(self) -> frozenset[str]:
        """Return the extensions handled by this extractor."""
        return frozenset({".zip", ".oiv"})

    def can_handle(self, archive: Path) -> bool:
        """Return whether ``archive`` looks like a zip container."""
        if archive.suffix.lower() in self.supported_suffixes:
            return True
        return zipfile.is_zipfile(archive)

    def extract(self, archive: Path, destination: Path) -> None:
        """Extract every member of ``archive`` into ``destination``."""
        fs.ensure_directory(destination)
        try:
            with zipfile.ZipFile(archive) as bundle:
                for member in bundle.infolist():
                    self._extract_member(bundle, member, destination)
        except zipfile.BadZipFile as error:
            raise ArchiveExtractionError(
                "Archive is corrupted or not a zip file", archive=str(archive)
            ) from error

    @staticmethod
    def _extract_member(
        bundle: zipfile.ZipFile, member: zipfile.ZipInfo, destination: Path
    ) -> None:
        """Write a single zip member, rejecting path traversal attempts."""
        name = member.filename.replace("\\", "/")
        if not name or name.endswith("/"):
            fs.ensure_directory(fs.safe_join(destination, name.rstrip("/") or "."))
            return
        target = fs.safe_join(destination, PurePosixPath(name))
        fs.ensure_directory(target.parent)
        with bundle.open(member) as source, target.open("wb") as sink:
            shutil.copyfileobj(source, sink)


class SevenZipExtractor:
    """Handles ``.7z`` archives via the optional ``py7zr`` dependency."""

    @property
    def supported_suffixes(self) -> frozenset[str]:
        """Return the extensions handled by this extractor."""
        return frozenset({".7z"})

    def can_handle(self, archive: Path) -> bool:
        """Return whether ``archive`` has a ``.7z`` extension."""
        return archive.suffix.lower() in self.supported_suffixes

    def extract(self, archive: Path, destination: Path) -> None:
        """Extract ``archive`` using ``py7zr``.

        Raises:
            DependencyMissingError: When ``py7zr`` is not installed.
        """
        try:
            import py7zr  # type: ignore[import-untyped]
        except ImportError as error:
            raise DependencyMissingError(
                "Install the 'py7zr' package to open .7z archives", archive=str(archive)
            ) from error

        fs.ensure_directory(destination)
        try:
            with py7zr.SevenZipFile(archive, mode="r") as bundle:
                self._reject_unsafe_names(bundle.getnames(), destination)
                bundle.extractall(path=str(destination))
        except Exception as error:  # noqa: BLE001 - py7zr raises many types
            raise ArchiveExtractionError(
                "Could not extract 7z archive", archive=str(archive), detail=str(error)
            ) from error

    @staticmethod
    def _reject_unsafe_names(names: list[str], destination: Path) -> None:
        """Validate every member name before extraction starts."""
        for name in names:
            fs.safe_join(destination, PurePosixPath(name.replace("\\", "/")))


class RarExtractor:
    """Handles ``.rar`` archives via ``rarfile``, UnRAR/WinRAR or 7-Zip.

    RAR is not a format Python can open on its own, so the extractor tries the
    ``rarfile`` package first and falls back to whichever archiver is installed
    on the machine. Both WinRAR and 7-Zip are auto-detected, which means the
    common case needs no configuration at all.
    """

    def __init__(
        self, seven_zip_path: Path | None = None, unrar_path: Path | None = None
    ) -> None:
        self._seven_zip_path = seven_zip_path
        self._unrar_path = unrar_path

    @property
    def supported_suffixes(self) -> frozenset[str]:
        """Return the extensions handled by this extractor."""
        return frozenset({".rar"})

    def can_handle(self, archive: Path) -> bool:
        """Return whether ``archive`` has a ``.rar`` extension."""
        return archive.suffix.lower() in self.supported_suffixes

    def extract(self, archive: Path, destination: Path) -> None:
        """Extract ``archive``, preferring ``rarfile`` over the CLI fallbacks."""
        fs.ensure_directory(destination)
        if self._extract_with_rarfile(archive, destination):
            return

        unrar = self._resolve_unrar()
        if unrar is not None and self._extract_with_cli(
            unrar,
            # UnRAR wants the output folder last, with a trailing separator.
            lambda staging: [str(unrar), "x", "-y", "-idq", str(archive), f"{staging}\\"],
            archive,
            destination,
        ):
            return

        seven_zip = self._resolve_seven_zip()
        if seven_zip is not None and self._extract_with_cli(
            seven_zip,
            lambda staging: [str(seven_zip), "x", "-y", f"-o{staging}", str(archive)],
            archive,
            destination,
        ):
            return

        raise DependencyMissingError(
            "Opening .rar archives needs WinRAR or 7-Zip installed, or the "
            "'rarfile' Python package. Install one of them, or set the path in "
            "Settings.",
            archive=str(archive),
        )

    def _extract_with_rarfile(self, archive: Path, destination: Path) -> bool:
        """Try the ``rarfile`` backend; return whether it succeeded."""
        try:
            import rarfile  # type: ignore[import-untyped]
        except ImportError:
            return False

        # rarfile shells out to UnRAR and only looks for it on PATH, where a
        # normal WinRAR installation never puts it.
        unrar = self._resolve_unrar()
        if unrar is not None:
            rarfile.UNRAR_TOOL = str(unrar)

        try:
            with rarfile.RarFile(archive) as bundle:
                for name in bundle.namelist():
                    fs.safe_join(destination, PurePosixPath(name.replace("\\", "/")))
                bundle.extractall(path=str(destination))
            return True
        except Exception as error:  # noqa: BLE001 - missing unrar binary etc.
            _LOGGER.debug("rarfile backend unavailable for %s: %s", archive, error)
            return False

    def _extract_with_cli(
        self,
        executable: Path,
        build_command: Callable[[Path], list[str]],
        archive: Path,
        destination: Path,
    ) -> bool:
        """Run an external archiver, containing its output inside ``destination``.

        The archiver writes into a staging folder below ``destination``, so an
        entry trying to climb out of the extraction folder still lands inside
        the workspace. The content is then moved up through
        :func:`~gta_mod_manager.utils.fs.safe_join`.
        """
        staging = fs.ensure_directory(destination / constants.CLI_EXTRACTION_STAGING_DIR)
        command = build_command(staging)

        try:
            completed = subprocess.run(  # noqa: S603 - executable is resolved, not user text
                command, capture_output=True, check=False
            )
        except OSError as error:
            _LOGGER.warning("Could not run %s: %s", executable.name, error)
            fs.delete_tree(staging)
            return False

        if completed.returncode != 0:
            _LOGGER.warning(
                "%s failed for %s: %s",
                executable.name,
                archive.name,
                completed.stderr.decode(errors="replace").strip()
                or completed.stdout.decode(errors="replace").strip(),
            )
            fs.delete_tree(staging)
            return False

        self._move_staged_content(staging, destination)
        fs.delete_tree(staging)
        _LOGGER.info("Extracted %s with %s", archive.name, executable.name)
        return True

    @staticmethod
    def _move_staged_content(staging: Path, destination: Path) -> None:
        """Move everything the archiver wrote from ``staging`` into place."""
        for source in fs.iter_files(staging):
            relative = source.relative_to(staging).as_posix()
            fs.move_file(source, fs.safe_join(destination, PurePosixPath(relative)))

    def _resolve_unrar(self) -> Path | None:
        """Return a usable UnRAR/WinRAR executable, if one can be found."""
        return self._first_available(
            self._unrar_path, constants.UNRAR_COMMAND_NAMES, constants.UNRAR_INSTALL_PATHS
        )

    def _resolve_seven_zip(self) -> Path | None:
        """Return a usable 7-Zip executable, if one can be found."""
        return self._first_available(
            self._seven_zip_path,
            constants.SEVEN_ZIP_COMMAND_NAMES,
            constants.SEVEN_ZIP_INSTALL_PATHS,
        )

    @staticmethod
    def _first_available(
        configured: Path | None, command_names: tuple[str, ...], install_paths: tuple[str, ...]
    ) -> Path | None:
        """Return the configured tool, else one found on PATH or installed."""
        if configured is not None and configured.is_file():
            return configured
        for name in command_names:
            located = shutil.which(name)
            if located:
                return Path(located)
        for candidate in install_paths:
            path = Path(candidate)
            if path.is_file():
                return path
        return None


class ExtractorRegistry:
    """Chooses the right extractor for a given archive."""

    def __init__(self, extractors: tuple[object, ...] | None = None) -> None:
        self._extractors: tuple[object, ...] = extractors or (
            ZipExtractor(),
            SevenZipExtractor(),
            RarExtractor(),
        )

    @property
    def supported_suffixes(self) -> frozenset[str]:
        """Return every extension the registered extractors can open."""
        result: set[str] = set()
        for extractor in self._extractors:
            result |= extractor.supported_suffixes  # type: ignore[attr-defined]
        return frozenset(result)

    def is_archive(self, path: Path) -> bool:
        """Return whether ``path`` is an archive this registry understands."""
        return path.suffix.lower() in constants.ARCHIVE_EXTENSIONS

    def find(self, archive: Path) -> object:
        """Return the extractor able to open ``archive``.

        Raises:
            UnsupportedArchiveError: When no extractor matches.
        """
        for extractor in self._extractors:
            if extractor.can_handle(archive):  # type: ignore[attr-defined]
                return extractor
        raise UnsupportedArchiveError(
            "No extractor available for this archive format",
            archive=str(archive),
            suffix=archive.suffix,
        )

    def extract(self, archive: Path, destination: Path) -> Path:
        """Extract ``archive`` into ``destination`` and return the destination."""
        extractor = self.find(archive)
        _LOGGER.info("Extracting %s with %s", archive.name, type(extractor).__name__)
        extractor.extract(archive, destination)  # type: ignore[attr-defined]
        return destination
