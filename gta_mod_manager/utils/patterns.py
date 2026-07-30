"""Glob-style matching used by the root-installation whitelist."""

from __future__ import annotations

from fnmatch import fnmatch
from pathlib import PurePosixPath
from typing import Iterable


def matches_any(name: str, patterns: Iterable[str]) -> bool:
    """Return whether ``name`` matches at least one case-insensitive pattern."""
    lowered = name.lower()
    return any(fnmatch(lowered, pattern.lower()) for pattern in patterns)


def first_match(name: str, patterns: Iterable[str]) -> str | None:
    """Return the first pattern that ``name`` matches, or ``None``."""
    lowered = name.lower()
    for pattern in patterns:
        if fnmatch(lowered, pattern.lower()):
            return pattern
    return None


def path_contains_directory(relative: PurePosixPath, directory_names: Iterable[str]) -> bool:
    """Return whether any folder in ``relative`` is one of ``directory_names``."""
    wanted = {name.lower() for name in directory_names}
    return any(part.lower() in wanted for part in relative.parts[:-1])


def top_directory(relative: PurePosixPath) -> str | None:
    """Return the first folder component of ``relative``, if it has one."""
    parts = relative.parts
    return parts[0] if len(parts) > 1 else None


def strip_leading_directories(relative: PurePosixPath, names: Iterable[str]) -> PurePosixPath:
    """Remove leading folders whose name is in ``names``.

    Mod archives are frequently wrapped in a folder named after the mod; this
    helper normalises ``MyMod v1.2/mods/update/...`` to ``mods/update/...``.
    """
    wanted = {name.lower() for name in names}
    parts = list(relative.parts)
    while len(parts) > 1 and parts[0].lower() in wanted:
        parts.pop(0)
    return PurePosixPath(*parts) if parts else relative
