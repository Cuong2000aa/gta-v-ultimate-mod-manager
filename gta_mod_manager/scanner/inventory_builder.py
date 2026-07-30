"""Builds a :class:`FileInventory` from an extracted folder."""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from gta_mod_manager.core import constants
from gta_mod_manager.core.logging_setup import get_logger
from gta_mod_manager.models.mod_file import FileInventory, ModFile
from gta_mod_manager.utils import fs, hashing

_LOGGER = get_logger("scanner.inventory")

#: Files that carry no information and only pollute the preview list.
_IGNORED_NAMES = frozenset({"thumbs.db", "desktop.ini", ".ds_store"})
_IGNORED_DIRECTORIES = frozenset({"__macosx", ".git", ".svn"})

#: Hashing every byte of a multi-gigabyte pack is wasteful during analysis.
_HASH_SIZE_LIMIT = 64 * 1024 * 1024


class InventoryBuilder:
    """Walks an extracted package and produces an immutable inventory.

    Args:
        max_depth: Directory depth limit, guarding against pathological trees.
        compute_hashes: Whether to hash files (skipped for very large ones).
    """

    def __init__(
        self,
        *,
        max_depth: int = constants.MAX_SCAN_DEPTH,
        compute_hashes: bool = True,
    ) -> None:
        self._max_depth = max_depth
        self._compute_hashes = compute_hashes

    def build(self, root: Path) -> FileInventory:
        """Return the inventory of every relevant file under ``root``."""
        root = fs.normalise(root)
        files: list[ModFile] = []
        for path in fs.iter_files(root, max_depth=self._max_depth):
            entry = self._describe(root, path)
            if entry is not None:
                files.append(entry)
        files.sort(key=lambda item: str(item.relative_path).lower())
        _LOGGER.debug("Inventoried %d file(s) under %s", len(files), root)
        return FileInventory(root=root, files=tuple(files))

    def _describe(self, root: Path, path: Path) -> ModFile | None:
        """Return a :class:`ModFile` for ``path``, or ``None`` when ignored."""
        try:
            relative = path.relative_to(root)
        except ValueError:  # pragma: no cover - iter_files stays below root
            return None

        if path.name.lower() in _IGNORED_NAMES:
            return None
        if any(part.lower() in _IGNORED_DIRECTORIES for part in relative.parts[:-1]):
            return None

        try:
            size = path.stat().st_size
        except OSError:
            _LOGGER.warning("Could not stat %s", path)
            return None

        digest: str | None = None
        if self._compute_hashes and size <= _HASH_SIZE_LIMIT:
            try:
                digest = hashing.sha256_file(path)
            except OSError:
                digest = None

        return ModFile(
            absolute_path=path,
            relative_path=PurePosixPath(relative.as_posix()),
            size_bytes=size,
            sha256=digest,
        )
