"""Detect and list leftover ENB / ReShade-style graphics files in the game root."""

from __future__ import annotations

from pathlib import Path

_ENB_CONFIG_NAMES: tuple[str, ...] = (
    "enblocal.ini",
    "enbseries.ini",
)

_ENB_PROXY_DLLS: tuple[str, ...] = (
    "d3d11.dll",
    "d3d10.dll",
    "dxgi.dll",
)

#: Exact filenames that are safe to quarantine when ENB is incomplete.
_ENB_EXACT_FILES: tuple[str, ...] = (
    "enblocal.ini",
    "enbseries.ini",
    "enbhost.exe",
    "enblens.fx",
    "enbdepthoffield.fx",
    "enbeffect.fx",
    "enbeffectprepass.fx",
    "enbbloom.fx",
    "enbsmaa.fx",
)


def has_enb_config(game_root: Path) -> bool:
    """Return whether classic ENB ini files sit in ``game_root``."""
    return any((game_root / name).is_file() for name in _ENB_CONFIG_NAMES)


def has_enb_proxy_dll(game_root: Path) -> bool:
    """Return whether a DirectX proxy DLL used by ENB is present."""
    return any((game_root / name).is_file() for name in _ENB_PROXY_DLLS)


def list_enb_leftover_files(game_root: Path) -> tuple[str, ...]:
    """Return basenames of ENB config/shader leftovers in the game root.

    Does **not** include proxy DLLs (``d3d11.dll`` / ``dxgi.dll``) — those may
    be shared with ReShade or other tools and need a deliberate full ENB wipe.
    """
    root = game_root.resolve()
    names: list[str] = []
    seen: set[str] = set()

    def add(path: Path) -> None:
        if not path.is_file():
            return
        try:
            if path.parent.resolve() != root:
                return
        except OSError:
            return
        name = path.name
        key = name.lower()
        if key in seen:
            return
        seen.add(key)
        names.append(name)

    for name in _ENB_EXACT_FILES:
        add(root / name)

    try:
        for path in root.iterdir():
            if not path.is_file():
                continue
            lower = path.name.lower()
            if lower.startswith("enb") and lower.endswith((".fx", ".ini", ".txt", ".xml")):
                add(path)
    except OSError:
        pass

    return tuple(sorted(names, key=str.lower))
