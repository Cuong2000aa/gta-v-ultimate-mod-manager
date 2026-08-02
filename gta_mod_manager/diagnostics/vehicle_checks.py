"""Detect orphan DLC packs and broken vehicle stream entries in mods RPFs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fivefury import RpfArchive
from fivefury.crypto import ensure_game_crypto
from fivefury.rpf.entries import RpfBinaryFileEntry, RpfResourceFileEntry
from fivefury.rpf.utils import _is_rsc7

from gta_mod_manager.core import constants
from gta_mod_manager.core.logging_setup import get_logger
from gta_mod_manager.models.mod_package import InstalledMod
from gta_mod_manager.plugins.gta_v.rpf_archive import split_member_path

_LOGGER = get_logger("diagnostics.vehicle_checks")


@dataclass(frozen=True, slots=True)
class OrphanDlcPack:
    """A dlcpacks folder that is not owned by any library record."""

    pack_name: str
    path: Path


@dataclass(frozen=True, slots=True)
class BadVehicleStreamEntry:
    """A ``.yft`` / ``.ytd`` in mods ``vehicles.rpf`` that is not a healthy resource."""

    member_path: str
    entry_type: str
    reason: str


@dataclass(frozen=True, slots=True)
class UnhealthyReplaceMember:
    """A library-claimed replace member that is missing or typed wrong."""

    mod_id: str
    display_name: str
    member_path: str
    reason: str


def tracked_dlc_pack_names(installed: tuple[InstalledMod, ...] | list[InstalledMod]) -> set[str]:
    """Return lower-cased pack names claimed by the library (and dlclist records)."""
    names: set[str] = set()
    for mod in installed:
        for pack in mod.dlc_packs:
            cleaned = pack.strip().strip("/").lower()
            if cleaned:
                names.add(cleaned)
        for record in mod.installed_files:
            pack_from_target = _pack_name_from_mods_path(record.target_path)
            if pack_from_target:
                names.add(pack_from_target)
            for member in record.archive_members:
                if not member.lower().startswith("dlclist:"):
                    continue
                pack = member.split(":", 1)[1].strip().strip("/").lower()
                if pack:
                    names.add(pack)
    return names


def stock_dlc_pack_names(game_root: Path) -> set[str]:
    """Return pack folders that already exist in the vanilla game ``dlcpacks``.

    Vehicle replaces often copy Rockstar packs (``patchday*``, ``mp*``, …) into
    ``mods/update/x64/dlcpacks``. Those mirrors must not be treated as orphans.
    """
    vanilla = game_root / Path(*constants.DLC_PACKS_RELATIVE.split("/"))
    if not vanilla.is_dir():
        return set()
    names: set[str] = set()
    try:
        for child in vanilla.iterdir():
            if child.is_dir():
                names.add(child.name.lower())
    except OSError as error:
        _LOGGER.warning("Could not list stock dlcpacks under %s: %s", vanilla, error)
    return names


def _pack_name_from_mods_path(path: Path) -> str | None:
    """Extract ``dlcpacks/<name>`` when ``path`` is under the mods folder."""
    parts = [part.lower() for part in path.parts]
    try:
        mods_index = parts.index(constants.MODS_FOLDER_NAME.lower())
        dlc_index = parts.index("dlcpacks", mods_index + 1)
    except ValueError:
        return None
    if dlc_index + 1 >= len(parts):
        return None
    name = parts[dlc_index + 1].strip()
    return name or None


def find_orphan_dlcpacks(
    game_root: Path,
    installed: tuple[InstalledMod, ...] | list[InstalledMod] = (),
) -> tuple[OrphanDlcPack, ...]:
    """List ``mods/.../dlcpacks/*`` folders not tracked by any installed mod."""
    packs_dir = (
        game_root
        / constants.MODS_FOLDER_NAME
        / Path(*constants.DLC_PACKS_RELATIVE.split("/"))
    )
    if not packs_dir.is_dir():
        return ()

    tracked = (
        tracked_dlc_pack_names(installed)
        | {name.lower() for name in constants.KNOWN_EXTERNAL_DLC_PACKS}
        | stock_dlc_pack_names(game_root)
    )
    orphans: list[OrphanDlcPack] = []
    try:
        children = sorted(packs_dir.iterdir(), key=lambda item: item.name.lower())
    except OSError as error:
        _LOGGER.warning("Could not list dlcpacks under %s: %s", packs_dir, error)
        return ()

    for child in children:
        if not child.is_dir():
            continue
        if child.name.lower() in tracked:
            continue
        orphans.append(OrphanDlcPack(pack_name=child.name, path=child))
    return tuple(orphans)


def find_bad_vehicle_stream_entries(mods_x64e: Path) -> tuple[BadVehicleStreamEntry, ...]:
    """Find ``.yft``/``.ytd`` entries stored as binary (or RSC7-as-binary) in mods x64e."""
    if not mods_x64e.is_file():
        return ()

    ensure_game_crypto()
    bad: list[BadVehicleStreamEntry] = []
    nested_name = constants.VEHICLE_STREAM_NESTED_RPF
    try:
        with RpfArchive.from_path(str(mods_x64e)) as archive:
            nested_entry = archive.find_entry(nested_name)
            if nested_entry is None:
                return ()
            nested = archive.load_nested_archive(nested_entry)
            if nested is None:
                return ()
            for entry in nested.iter_entries():
                name = entry.name
                suffix = Path(name).suffix.lower()
                if suffix not in constants.VEHICLE_STREAM_EXTENSIONS:
                    continue
                member_path = f"{nested_name}/{name}"
                problem = _classify_stream_problem(nested, entry)
                if problem is None:
                    continue
                bad.append(
                    BadVehicleStreamEntry(
                        member_path=member_path,
                        entry_type=type(entry).__name__,
                        reason=problem,
                    )
                )
    except Exception as error:  # noqa: BLE001 - diagnostics must not crash the UI
        _LOGGER.warning("Could not scan vehicle stream in %s: %s", mods_x64e, error)
        return ()
    return tuple(bad)


def find_unhealthy_replace_members(
    mods_x64e: Path,
    installed: tuple[InstalledMod, ...] | list[InstalledMod],
) -> tuple[UnhealthyReplaceMember, ...]:
    """Check library-claimed vehicle stream members still look healthy.

    Only members recorded against ``mods_x64e`` itself are checked. Ped pack
    imports (``umm_peds/dlc.rpf`` → ``peds.rpf/...``) are ignored here.
    """
    if not mods_x64e.is_file() or not installed:
        return ()

    target = mods_x64e.resolve()
    claimed: list[tuple[InstalledMod, str]] = []
    for mod in installed:
        for record in mod.installed_files:
            try:
                if record.target_path.resolve() != target:
                    continue
            except OSError:
                continue
            for member in record.archive_members:
                normalised = member.replace("\\", "/").strip("/")
                lower = normalised.lower()
                if lower.startswith("dlclist:") or lower.startswith("pedmeta:"):
                    continue
                if lower.startswith(f"{constants.ADDON_PEDS_STREAM_ARCHIVE}/"):
                    continue
                suffix = Path(normalised).suffix.lower()
                if suffix not in constants.VEHICLE_STREAM_EXTENSIONS:
                    continue
                claimed.append((mod, normalised))
    if not claimed:
        return ()

    ensure_game_crypto()
    unhealthy: list[UnhealthyReplaceMember] = []
    try:
        with RpfArchive.from_path(str(mods_x64e)) as archive:
            for mod, member_path in claimed:
                reason = _member_health_reason(archive, member_path)
                if reason is None:
                    continue
                unhealthy.append(
                    UnhealthyReplaceMember(
                        mod_id=mod.mod_id,
                        display_name=mod.display_name,
                        member_path=member_path,
                        reason=reason,
                    )
                )
    except Exception as error:  # noqa: BLE001
        _LOGGER.warning(
            "Could not verify replace members in %s: %s", mods_x64e, error
        )
        return ()
    return tuple(unhealthy)


def _classify_stream_problem(archive: RpfArchive, entry: object) -> str | None:
    """Return a short reason when a vehicle stream entry is the wrong type."""
    if isinstance(entry, RpfResourceFileEntry):
        return None
    if isinstance(entry, RpfBinaryFileEntry):
        try:
            raw = archive.read_entry_raw(entry)
        except Exception:  # noqa: BLE001
            return "binary entry (unreadable); vehicle streams must be resources"
        if raw and _is_rsc7(bytes(raw)):
            return "binary entry whose body looks like RSC7; should be a resource"
        return "binary entry; vehicle .yft/.ytd must be RpfResourceFileEntry"
    return f"unexpected entry type {type(entry).__name__}"


def _member_health_reason(archive: RpfArchive, member_path: str) -> str | None:
    """Return why ``member_path`` is unhealthy, or ``None`` when OK."""
    nested_path, leaf = split_member_path(member_path)
    target = archive
    if nested_path is not None:
        nested_entry = archive.find_entry(nested_path)
        if nested_entry is None:
            return "nested archive missing"
        loaded = archive.load_nested_archive(nested_entry)
        if loaded is None:
            return "nested archive could not be loaded"
        target = loaded
    entry = _find_by_name(target, leaf)
    if entry is None:
        return "member missing from mods archive"
    return _classify_stream_problem(target, entry)


def _find_by_name(archive: RpfArchive, leaf: str):
    needle = leaf.replace("\\", "/").rsplit("/", 1)[-1].lower()
    for entry in archive.iter_entries():
        if entry.name.lower() == needle:
            return entry
    return archive.find_entry(leaf)
