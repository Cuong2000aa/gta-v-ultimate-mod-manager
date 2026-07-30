"""Value objects describing individual files found inside a mod package."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from gta_mod_manager.core import constants


@dataclass(frozen=True, slots=True)
class ModFile:
    """A single file discovered while scanning an extracted mod package.

    Attributes:
        absolute_path: Location of the file inside the temporary workspace.
        relative_path: POSIX-style path relative to the package root.
        size_bytes: File size in bytes.
        sha256: Content hash, computed lazily by the scanner when requested.
    """

    absolute_path: Path
    relative_path: PurePosixPath
    size_bytes: int
    sha256: str | None = None

    @property
    def name(self) -> str:
        """Return the file name including its extension."""
        return self.relative_path.name

    @property
    def lower_name(self) -> str:
        """Return the lowercase file name, handy for case-insensitive rules."""
        return self.relative_path.name.lower()

    @property
    def suffix(self) -> str:
        """Return the lowercase file extension including the leading dot."""
        return self.relative_path.suffix.lower()

    @property
    def parts_lower(self) -> tuple[str, ...]:
        """Return the lowercase path components of :attr:`relative_path`."""
        return tuple(part.lower() for part in self.relative_path.parts)

    @property
    def is_archive(self) -> bool:
        """Return whether the file is an archive the scanner can open."""
        return self.suffix in constants.ARCHIVE_EXTENSIONS

    @property
    def is_game_asset(self) -> bool:
        """Return whether the file is a packed GTA V game asset."""
        return self.suffix in constants.GAME_ASSET_EXTENSIONS

    @property
    def is_image(self) -> bool:
        """Return whether the file is a picture usable as preview image."""
        return self.suffix in constants.IMAGE_EXTENSIONS

    def with_hash(self, digest: str) -> "ModFile":
        """Return a copy carrying the supplied content hash."""
        return ModFile(
            absolute_path=self.absolute_path,
            relative_path=self.relative_path,
            size_bytes=self.size_bytes,
            sha256=digest,
        )


@dataclass(frozen=True, slots=True)
class FileInventory:
    """Immutable snapshot of every file inside an extracted package."""

    root: Path
    files: tuple[ModFile, ...]

    @property
    def total_size(self) -> int:
        """Return the summed size of every file in bytes."""
        return sum(item.size_bytes for item in self.files)

    @property
    def count(self) -> int:
        """Return the number of files in the inventory."""
        return len(self.files)

    def by_suffix(self, *suffixes: str) -> tuple[ModFile, ...]:
        """Return files whose extension matches any of ``suffixes``."""
        wanted = {suffix.lower() for suffix in suffixes}
        return tuple(item for item in self.files if item.suffix in wanted)

    def by_name(self, *names: str) -> tuple[ModFile, ...]:
        """Return files whose name matches any of ``names`` (case-insensitive)."""
        wanted = {name.lower() for name in names}
        return tuple(item for item in self.files if item.lower_name in wanted)

    def in_directory(self, directory_name: str) -> tuple[ModFile, ...]:
        """Return files located anywhere under a folder called ``directory_name``."""
        needle = directory_name.lower()
        return tuple(item for item in self.files if needle in item.parts_lower[:-1])

    def has_name(self, name: str) -> bool:
        """Return whether a file with the given name exists."""
        return bool(self.by_name(name))

    def has_suffix(self, suffix: str) -> bool:
        """Return whether at least one file uses the given extension."""
        return bool(self.by_suffix(suffix))

    def preview_images(self) -> tuple[ModFile, ...]:
        """Return image files ordered by descending size (best preview first)."""
        images = [item for item in self.files if item.is_image and item.suffix != ".dds"]
        return tuple(sorted(images, key=lambda item: item.size_bytes, reverse=True))
