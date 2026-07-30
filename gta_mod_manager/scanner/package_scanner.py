"""The scanner: turns whatever the user dropped into a flat file inventory.

Accepted input is a folder, a loose file (``.dll``, ``.asi``, ``.xml`` ...) or
an archive (``.zip``, ``.7z``, ``.rar``, ``.oiv``). Nested archives are
extracted recursively up to
:data:`~gta_mod_manager.core.constants.MAX_NESTED_ARCHIVE_DEPTH`, because mod
authors regularly ship a zip inside a zip.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from gta_mod_manager.core import constants
from gta_mod_manager.core.events import new_operation_id
from gta_mod_manager.core.exceptions import ScanError
from gta_mod_manager.core.logging_setup import get_logger
from gta_mod_manager.core.progress import NullProgressReporter
from gta_mod_manager.core.protocols import ProgressReporter
from gta_mod_manager.models.mod_file import FileInventory
from gta_mod_manager.scanner.extractors import ExtractorRegistry
from gta_mod_manager.scanner.inventory_builder import InventoryBuilder
from gta_mod_manager.utils import fs

_LOGGER = get_logger("scanner.package")

#: Folder names mod authors wrap their content in; stripped when flattening.
_WRAPPER_FOLDER_HINTS = frozenset({"__extracted__"})

#: Folder names that carry installation meaning and must never be flattened
#: away: descending into ``scripts/`` would turn a .NET script package into a
#: bag of loose files and lose the only hint about where it belongs.
_STRUCTURAL_FOLDERS = frozenset(
    {
        constants.MODS_FOLDER_NAME,
        constants.UPDATE_FOLDER_NAME,
        "x64",
        "dlcpacks",
        "common",
        "data",
        *(name.lower() for name in constants.ALLOWED_ROOT_DIRECTORIES),
    }
)

#: Files that mark a folder as a DLC pack root, which is also structural.
_PACK_ROOT_MARKERS = frozenset({"setup2.xml", "content.xml"})


@dataclass(frozen=True, slots=True)
class ScanOptions:
    """Knobs controlling one scan.

    Attributes:
        compute_hashes: Hash files so duplicates and conflicts can be detected.
        max_nested_depth: How deep nested archives are unpacked.
        flatten_single_root: Descend into a single wrapping folder.
    """

    compute_hashes: bool = True
    max_nested_depth: int = constants.MAX_NESTED_ARCHIVE_DEPTH
    flatten_single_root: bool = True


class PackageScanner:
    """Extracts and inventories a user supplied mod source."""

    def __init__(
        self,
        extractors: ExtractorRegistry | None = None,
        options: ScanOptions | None = None,
    ) -> None:
        self._extractors = extractors or ExtractorRegistry()
        self._options = options or ScanOptions()
        self._builder = InventoryBuilder(compute_hashes=self._options.compute_hashes)

    def scan(
        self,
        source: Path,
        workspace: Path,
        reporter: ProgressReporter | None = None,
    ) -> FileInventory:
        """Prepare ``source`` inside ``workspace`` and return its inventory.

        Args:
            source: Archive, loose file or folder chosen by the user.
            workspace: Temporary directory that receives extracted content.
            reporter: Optional progress sink.

        Returns:
            The inventory of every file the package contains.

        Raises:
            ScanError: When ``source`` does not exist or cannot be read.
        """
        reporter = reporter or NullProgressReporter()
        operation_id = new_operation_id()
        source = fs.normalise(source)
        if not source.exists():
            raise ScanError("Source does not exist", source=str(source))

        reporter.start(operation_id, f"Scanning {source.name}", total=3)
        content_root = self._materialise(source, workspace)
        reporter.advance(operation_id, 1, "Unpacking nested archives")

        self._expand_nested_archives(content_root, depth=1)
        reporter.advance(operation_id, 2, "Indexing files")

        if self._options.flatten_single_root:
            content_root = self._descend_into_single_folder(content_root)

        inventory = self._builder.build(content_root)
        reporter.finish(operation_id, f"Found {inventory.count} file(s)")
        _LOGGER.info(
            "Scanned %s: %d file(s), %s",
            source.name,
            inventory.count,
            fs.human_size(inventory.total_size),
        )
        return inventory

    def _materialise(self, source: Path, workspace: Path) -> Path:
        """Copy or extract ``source`` into ``workspace`` and return the root."""
        target = fs.ensure_directory(workspace / "__extracted__")
        if source.is_dir():
            self._copy_tree(source, target)
            return target
        if self._extractors.is_archive(source):
            self._extractors.extract(source, target)
            return target
        fs.copy_file(source, target / source.name)
        return target

    @staticmethod
    def _copy_tree(source: Path, target: Path) -> None:
        """Copy a folder the user dropped, preserving its structure."""
        for item in fs.iter_files(source):
            relative = item.relative_to(source)
            fs.copy_file(item, target / relative)

    def _expand_nested_archives(self, root: Path, depth: int) -> None:
        """Recursively extract archives found inside ``root``.

        Each nested archive is unpacked next to itself into a folder named
        after the archive, then the archive file is deleted so the inventory
        only reports real content.
        """
        if depth > self._options.max_nested_depth:
            return
        nested = [
            path
            for path in fs.iter_files(root)
            if path.suffix.lower() in constants.ARCHIVE_EXTENSIONS
        ]
        for archive in nested:
            destination = fs.unique_path(archive.parent / fs.sanitise_name(archive.stem))
            try:
                self._extractors.extract(archive, destination)
            except Exception as error:  # noqa: BLE001 - a broken inner archive
                _LOGGER.warning("Skipping nested archive %s: %s", archive.name, error)
                continue
            fs.delete_file(archive)
            self._expand_nested_archives(destination, depth + 1)

    @staticmethod
    def _descend_into_single_folder(root: Path) -> Path:
        """Skip wrapper folders such as ``MyMod v1.2/`` around the content."""
        current = root
        for _ in range(4):
            children = list(current.iterdir())
            if len(children) != 1 or not children[0].is_dir():
                break
            candidate = children[0]
            name = candidate.name.lower()
            if name in _WRAPPER_FOLDER_HINTS or name in _STRUCTURAL_FOLDERS:
                break
            if any(
                (candidate / marker).is_file() for marker in _PACK_ROOT_MARKERS
            ):
                break
            current = candidate
        return current
