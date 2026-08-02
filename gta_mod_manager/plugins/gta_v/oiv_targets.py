"""Map OpenIV virtual game paths onto mods-folder ``.rpf`` targets.

OpenIV package descriptors use roots such as ``/common/data/...`` and
``/dlc_patch/<pack>/...`` that do not contain a ``.rpf`` segment. Those paths
still live inside archives; this module resolves them to a safe
``mods/<archive>`` + member path pair the installer can import.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from gta_mod_manager.core import constants


@dataclass(frozen=True, slots=True)
class OivArchiveTarget:
    """One OpenIV virtual path resolved to a mods ``.rpf`` import."""

    #: Path relative to the game root (and mirrored under ``mods/``).
    relative_archive: Path
    #: Member path inside that archive (``/`` separators, no leading slash).
    member_path: str
    #: ``True`` when this is a DLC pack patch (may be large to mirror).
    is_dlc_patch: bool = False


def resolve_openiv_virtual_path(destination: PurePosixPath) -> OivArchiveTarget | None:
    """Resolve an OpenIV destination to a mods-folder archive import.

    Returns:
        The archive + member mapping, or ``None`` when the path is not a known
        virtual OpenIV game root.
    """
    parts = [part for part in destination.parts if part and part != "/"]
    if not parts:
        return None
    lower = [part.lower() for part in parts]

    # /common/data/... → update/update.rpf/common/data/...
    if lower[0] == "common":
        return OivArchiveTarget(
            relative_archive=Path(constants.UPDATE_ARCHIVE_RELATIVE),
            member_path="/".join(parts),
        )

    # /x64/data/... → update/update.rpf/x64/data/...
    if lower[0] == "x64" and len(lower) >= 2 and lower[1] == "data":
        return OivArchiveTarget(
            relative_archive=Path(constants.UPDATE_ARCHIVE_RELATIVE),
            member_path="/".join(parts),
        )

    # /dlc_patch/<pack>/... → update/x64/dlcpacks/<pack>/dlc.rpf/...
    if lower[0] == "dlc_patch" and len(parts) >= 3:
        pack = parts[1]
        member = "/".join(parts[2:])
        if not member:
            return None
        return OivArchiveTarget(
            relative_archive=Path(*constants.DLC_PACKS_RELATIVE.split("/"))
            / pack
            / "dlc.rpf",
            member_path=member,
            is_dlc_patch=True,
        )

    return None
