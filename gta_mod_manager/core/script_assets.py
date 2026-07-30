"""Recognises ScriptHookVDotNet script assemblies inside a mod package.

Many script mods ship nothing but a bare ``.dll`` next to a readme that says
"drop this in your scripts folder". The name alone carries no signal, so the
file is identified by content instead: a managed Windows binary whose metadata
references the ScriptHookVDotNet assembly. Without this the manager would treat
``GTZ.dll`` as an unknown file and hide it inside ``mods``, where the game
never loads it.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path, PurePosixPath

from gta_mod_manager.core.logging_setup import get_logger

_LOGGER = get_logger("core.script_assets")

#: Extensions that can hold a compiled script assembly.
SCRIPT_ASSEMBLY_SUFFIXES: frozenset[str] = frozenset({".dll"})

#: Files that must travel with an assembly. Debug symbols are useless on their
#: own but script authors ship them, and they belong next to the ``.dll``.
SCRIPT_SIDECAR_SUFFIXES: frozenset[str] = frozenset({".pdb"})

#: Runtime/loader binaries that belong in the game root, not in ``scripts``.
LOADER_ASSEMBLY_NAMES: frozenset[str] = frozenset(
    {
        "scripthookv.dll",
        "dinput8.dll",
        "scripthookvdotnet.asi",
        "scripthookvdotnet.dll",
        "scripthookvdotnet2.dll",
        "scripthookvdotnet3.dll",
    }
)

#: Assembly reference present in every managed script built against SHVDN.
_SHVDN_REFERENCE = b"ScriptHookVDotNet"

#: Helper libraries a script may reference, keyed by the dependency tag they
#: imply. A script that draws a NativeUI menu crashes on load without it.
_LIBRARY_REFERENCES: dict[str, bytes] = {
    "requires_nativeui": b"NativeUI",
}

#: Reading beyond this is never needed: the CLI metadata sits near the front.
_SCAN_LIMIT = 8 * 1024 * 1024


def _read_head(path: Path) -> bytes:
    """Return the leading bytes of ``path``, or empty when unreadable."""
    try:
        return path.read_bytes()[:_SCAN_LIMIT]
    except OSError as error:
        _LOGGER.debug("Could not read %s: %s", path, error)
        return b""


def is_script_assembly(path: Path, name: str | None = None) -> bool:
    """Return whether ``path`` is a managed script built against SHVDN.

    Args:
        path: Absolute location of the candidate file.
        name: File name to test against the loader list; taken from ``path``
            when omitted.
    """
    file_name = (name or path.name).lower()
    if PurePosixPath(file_name).suffix not in SCRIPT_ASSEMBLY_SUFFIXES:
        return False
    if file_name in LOADER_ASSEMBLY_NAMES:
        return False
    head = _read_head(path)
    return head[:2] == b"MZ" and _SHVDN_REFERENCE in head


def script_library_tags(path: Path, name: str | None = None) -> frozenset[str]:
    """Return the dependency tags implied by the libraries ``path`` uses.

    A library never counts as a dependency of itself, so shipping
    ``NativeUI.dll`` does not raise a "NativeUI is missing" warning.
    """
    file_name = (name or path.name).lower()
    head = _read_head(path)
    if not head:
        return frozenset()
    return frozenset(
        tag
        for tag, marker in _LIBRARY_REFERENCES.items()
        if marker in head and file_name != f"{marker.decode().lower()}.dll"
    )


def script_assembly_paths(
    files: Iterable[tuple[Path, PurePosixPath]],
) -> frozenset[PurePosixPath]:
    """Return the package-relative paths that hold a SHVDN script assembly.

    Args:
        files: Pairs of absolute path and package-relative path.
    """
    return frozenset(
        relative
        for absolute, relative in files
        if is_script_assembly(absolute, relative.name)
    )
