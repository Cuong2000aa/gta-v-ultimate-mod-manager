"""Read-only view of a package that analyzer rules query.

Rules must not touch the filesystem directly: everything they need is exposed
here and cached, so a scan of a 5 GB pack is walked once instead of once per
rule.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from typing import Iterable

from gta_mod_manager.core import constants
from gta_mod_manager.core.logging_setup import get_logger
from gta_mod_manager.models.mod_file import FileInventory, ModFile

_LOGGER = get_logger("analyzer.context")

#: Reading more than this from a text file is never needed for classification.
_TEXT_PREVIEW_LIMIT = 256 * 1024

_TEXT_SUFFIXES = frozenset({".txt", ".md", ".ini", ".xml", ".meta", ".cs", ".vb", ".lua", ".log"})


@dataclass
class AnalysisContext:
    """Everything the analyzer rules are allowed to look at.

    Attributes:
        inventory: Files discovered by the scanner.
        source_name: Original archive or folder name; a strong naming signal.
    """

    inventory: FileInventory
    source_name: str = ""
    _text_cache: dict[Path, str] = field(default_factory=dict, repr=False)

    @property
    def files(self) -> tuple[ModFile, ...]:
        """Return every file in the package."""
        return self.inventory.files

    @cached_property
    def file_names(self) -> frozenset[str]:
        """Return every lowercase file name in the package."""
        return frozenset(item.lower_name for item in self.files)

    @cached_property
    def suffixes(self) -> frozenset[str]:
        """Return every lowercase file extension present."""
        return frozenset(item.suffix for item in self.files)

    @cached_property
    def directory_names(self) -> frozenset[str]:
        """Return every lowercase folder name appearing in any path."""
        names: set[str] = set()
        for item in self.files:
            names.update(item.parts_lower[:-1])
        return frozenset(names)

    @cached_property
    def searchable_text(self) -> str:
        """Return the lowercase source name plus every relative path.

        This single string powers all keyword rules, which keeps them cheap.
        """
        parts = [self.source_name.lower()]
        parts.extend(str(item.relative_path).lower() for item in self.files)
        return "\n".join(parts)

    def has_file(self, *names: str) -> bool:
        """Return whether any of ``names`` exists in the package."""
        return any(name.lower() in self.file_names for name in names)

    def has_suffix(self, *suffixes: str) -> bool:
        """Return whether any of ``suffixes`` is used by a file."""
        return any(suffix.lower() in self.suffixes for suffix in suffixes)

    def has_directory(self, *names: str) -> bool:
        """Return whether a folder with any of ``names`` exists."""
        return any(name.lower() in self.directory_names for name in names)

    def count_suffix(self, *suffixes: str) -> int:
        """Return how many files use any of ``suffixes``."""
        wanted = {suffix.lower() for suffix in suffixes}
        return sum(1 for item in self.files if item.suffix in wanted)

    def files_named(self, *names: str) -> tuple[ModFile, ...]:
        """Return the files whose name matches any of ``names``."""
        return self.inventory.by_name(*names)

    def files_with_suffix(self, *suffixes: str) -> tuple[ModFile, ...]:
        """Return the files whose extension matches any of ``suffixes``."""
        return self.inventory.by_suffix(*suffixes)

    def contains_keyword(self, *keywords: str) -> bool:
        """Return whether any keyword appears in a path or the source name."""
        haystack = self.searchable_text
        return any(keyword.lower() in haystack for keyword in keywords)

    def matched_keywords(self, keywords: Iterable[str]) -> tuple[str, ...]:
        """Return the keywords that appear in a path or the source name."""
        haystack = self.searchable_text
        return tuple(keyword for keyword in keywords if keyword.lower() in haystack)

    def read_text(self, file: ModFile) -> str:
        """Return the (cached, truncated, lowercase) text content of ``file``.

        Binary and oversized files yield an empty string so rules can call
        this unconditionally.
        """
        if file.suffix not in _TEXT_SUFFIXES or file.size_bytes > _TEXT_PREVIEW_LIMIT:
            return ""
        cached = self._text_cache.get(file.absolute_path)
        if cached is not None:
            return cached
        try:
            raw = file.absolute_path.read_bytes()[:_TEXT_PREVIEW_LIMIT]
            text = raw.decode("utf-8", errors="replace").lower()
        except OSError as error:
            _LOGGER.debug("Could not read %s: %s", file.absolute_path, error)
            text = ""
        self._text_cache[file.absolute_path] = text
        return text

    def any_text_contains(self, suffixes: Iterable[str], *needles: str) -> bool:
        """Return whether any file with one of ``suffixes`` contains a needle."""
        for file in self.files_with_suffix(*suffixes):
            text = self.read_text(file)
            if text and any(needle.lower() in text for needle in needles):
                return True
        return False

    @cached_property
    def game_asset_count(self) -> int:
        """Return how many packed GTA V assets the package ships."""
        return sum(1 for item in self.files if item.is_game_asset)

    @cached_property
    def is_mods_folder_layout(self) -> bool:
        """Return whether the package mirrors the ``mods`` folder structure."""
        return self.has_directory(constants.MODS_FOLDER_NAME) or self.has_directory(
            constants.UPDATE_FOLDER_NAME
        )
