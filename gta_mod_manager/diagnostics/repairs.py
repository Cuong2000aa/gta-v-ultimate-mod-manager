"""Safe one-click repairs for diagnostics findings."""

from __future__ import annotations

from pathlib import Path

from gta_mod_manager.core import constants
from gta_mod_manager.core.exceptions import InstallError
from gta_mod_manager.core.logging_setup import get_logger
from gta_mod_manager.core.result import Result
from gta_mod_manager.diagnostics.actions import (
    FIX_DELETE_ORPHAN_DLCPACKS,
    FIX_QUARANTINE_ENB_LEFTOVERS,
    FIX_RESTORE_VEHICLE_STREAM,
)
from gta_mod_manager.diagnostics.enb import list_enb_leftover_files
from gta_mod_manager.plugins.gta_v.rpf_archive import (
    remove_dlclist_entries,
    restore_stock_members,
    stock_archive_for_mods_copy,
)
from gta_mod_manager.utils import fs

_LOGGER = get_logger("diagnostics.repairs")

#: Filenames that must never be moved by the ENB quarantine repair.
_ENB_QUARANTINE_BLOCKLIST: frozenset[str] = frozenset(
    {
        "gta5.exe",
        "gta5_enhanced.exe",
        "playgtav.exe",
        "gtavlauncher.exe",
        "dinput8.dll",
        "scripthookv.dll",
        "openiv.asi",
        "d3d11.dll",
        "d3d10.dll",
        "d3d12.dll",
        "dxgi.dll",
        "d3dcompiler_47.dll",
    }
)


def apply_diagnostic_fix(
    game_root: Path,
    action: str,
    targets: tuple[str, ...] | list[str],
) -> Result[str]:
    """Apply a known diagnostics fix under ``game_root``.

    Orphan DLC / vehicle-stream repairs only touch ``mods/``.
    ENB quarantine moves leftover config/shaders from the game root into
    ``mods/_enb_quarantine_by_manager/`` (never deletes proxy DLLs).
    """
    unique = tuple(dict.fromkeys(item.strip() for item in targets if item and item.strip()))
    if not unique:
        return Result.fail("Nothing selected to repair", code="diagnostics.fix.empty")

    if action == FIX_DELETE_ORPHAN_DLCPACKS:
        return _delete_orphan_dlcpacks(game_root, unique)
    if action == FIX_RESTORE_VEHICLE_STREAM:
        return _restore_vehicle_stream(game_root, unique)
    if action == FIX_QUARANTINE_ENB_LEFTOVERS:
        return _quarantine_enb_leftovers(game_root, unique)
    return Result.fail(
        f"Unknown diagnostics fix action: {action}",
        code="diagnostics.fix.unknown",
    )


def _quarantine_enb_leftovers(
    game_root: Path, requested: tuple[str, ...]
) -> Result[str]:
    """Move ENB leftover files from the game root into a mods quarantine folder."""
    root = fs.normalise(game_root)
    allowed = set(list_enb_leftover_files(root))
    quarantine = fs.normalise(root.joinpath(*constants.ENB_QUARANTINE_FOLDER.split("/")))
    quarantine.mkdir(parents=True, exist_ok=True)

    moved: list[str] = []
    missing: list[str] = []
    skipped: list[str] = []

    for name in requested:
        base = Path(name).name
        if not base or base != name.replace("\\", "/").rsplit("/", 1)[-1]:
            return Result.fail(
                f"Refusing unsafe ENB target path: {name}",
                code="diagnostics.fix.unsafe_path",
            )
        if base.lower() in _ENB_QUARANTINE_BLOCKLIST:
            return Result.fail(
                f"Refusing to quarantine protected file: {base}",
                code="diagnostics.fix.unsafe_path",
            )
        if base not in allowed and base.lower() not in {item.lower() for item in allowed}:
            # Still allow exact ENB leftovers that disappeared from the live list
            # only when they match the enb* pattern and exist on disk.
            lower = base.lower()
            if not (
                lower.startswith("enb")
                and lower.endswith((".ini", ".fx", ".txt", ".xml", ".exe"))
            ):
                skipped.append(base)
                continue

        source = fs.normalise(root / base)
        if source.parent.resolve() != root.resolve():
            return Result.fail(
                f"Refusing path outside game root: {base}",
                code="diagnostics.fix.unsafe_path",
            )
        if not source.is_file():
            missing.append(base)
            continue

        destination = quarantine / base
        if destination.exists():
            stem = destination.stem
            suffix = destination.suffix
            index = 1
            while destination.exists():
                destination = quarantine / f"{stem}.{index}{suffix}"
                index += 1
        try:
            fs.move_file(source, destination)
        except OSError as error:
            return Result.fail(
                f"Could not quarantine '{base}': {error}",
                code="diagnostics.fix.move_failed",
            )
        moved.append(base)
        _LOGGER.info("Quarantined ENB leftover %s -> %s", source, destination)

    if not moved and missing and not skipped:
        return Result.fail(
            f"No ENB leftovers found to quarantine ({', '.join(missing)})",
            code="diagnostics.fix.not_found",
        )
    if not moved:
        detail = []
        if missing:
            detail.append(f"missing: {', '.join(missing)}")
        if skipped:
            detail.append(f"skipped: {', '.join(skipped)}")
        return Result.fail(
            "Nothing was quarantined" + (f" ({'; '.join(detail)})" if detail else ""),
            code="diagnostics.fix.not_found",
        )

    parts = [
        f"Moved {len(moved)} ENB leftover file(s) to {constants.ENB_QUARANTINE_FOLDER}/",
        f"({', '.join(moved)})",
    ]
    if missing:
        parts.append(f"; already gone: {', '.join(missing)}")
    if skipped:
        parts.append(f"; skipped: {', '.join(skipped)}")
    return Result.ok(" ".join(parts))


def _delete_orphan_dlcpacks(game_root: Path, pack_names: tuple[str, ...]) -> Result[str]:
    """Delete listed pack folders under mods dlcpacks and scrub dlclist."""
    packs_root = (
        game_root
        / constants.MODS_FOLDER_NAME
        / Path(*constants.DLC_PACKS_RELATIVE.split("/"))
    )
    packs_root = fs.normalise(packs_root)
    deleted: list[str] = []
    missing: list[str] = []

    for name in pack_names:
        candidate = fs.normalise(packs_root / name)
        if not fs.is_relative_to(candidate, packs_root):
            return Result.fail(
                f"Refusing to delete path outside mods dlcpacks: {name}",
                code="diagnostics.fix.unsafe_path",
            )
        if not candidate.is_dir():
            missing.append(name)
            continue
        try:
            fs.delete_tree(candidate)
        except OSError as error:
            return Result.fail(
                f"Could not delete orphan DLC pack '{name}': {error}",
                code="diagnostics.fix.delete_failed",
            )
        deleted.append(name)
        _LOGGER.info("Deleted orphan dlcpack %s", candidate)

    update_rpf = game_root / constants.MODS_FOLDER_NAME / constants.UPDATE_ARCHIVE_RELATIVE
    scrubbed = 0
    if deleted and update_rpf.is_file():
        try:
            scrubbed = remove_dlclist_entries(update_rpf, deleted)
        except InstallError as error:
            return Result.ok(
                f"Deleted {len(deleted)} orphan pack(s): {', '.join(deleted)}. "
                f"dlclist cleanup failed: {error}",
            ).with_warning(str(error))

    parts = [f"Deleted {len(deleted)} orphan DLC pack(s)"]
    if deleted:
        parts.append(f"({', '.join(deleted)})")
    if scrubbed:
        parts.append(f"and removed {scrubbed} dlclist entr(y/ies)")
    if missing:
        parts.append(f"; already gone: {', '.join(missing)}")
    if not deleted and missing:
        return Result.fail(
            f"No orphan packs were found to delete ({', '.join(missing)})",
            code="diagnostics.fix.not_found",
        )
    return Result.ok(" ".join(parts))


def _restore_vehicle_stream(game_root: Path, member_paths: tuple[str, ...]) -> Result[str]:
    """Restore stock ``.yft``/``.ytd`` members into the mods copy of x64e.rpf."""
    mods_archive = game_root / constants.MODS_FOLDER_NAME / constants.VEHICLE_STREAM_ARCHIVE
    if not mods_archive.is_file():
        return Result.fail(
            "mods/x64e.rpf is missing; nothing to restore into",
            code="diagnostics.fix.mods_x64e_missing",
        )
    try:
        stock = stock_archive_for_mods_copy(mods_archive, game_root)
    except InstallError as error:
        return Result.fail(str(error), code="diagnostics.fix.stock_map_failed")
    if not stock.is_file():
        # Fallthrough delete still works when mirrored stock is missing.
        _LOGGER.warning(
            "Stock %s missing; restore will delete members from mods for fallthrough",
            stock,
        )

    # Only allow vehicle stream members under the nested vehicles.rpf.
    allowed: list[str] = []
    for member in member_paths:
        normalised = member.replace("\\", "/").strip("/")
        suffix = Path(normalised).suffix.lower()
        if suffix not in constants.VEHICLE_STREAM_EXTENSIONS:
            return Result.fail(
                f"Refusing to restore non-vehicle-stream member: {member}",
                code="diagnostics.fix.unsafe_member",
            )
        if not normalised.lower().startswith(
            constants.VEHICLE_STREAM_NESTED_RPF.lower() + "/"
        ):
            return Result.fail(
                f"Refusing to restore member outside vehicles.rpf: {member}",
                code="diagnostics.fix.unsafe_member",
            )
        allowed.append(normalised)

    try:
        outcome = restore_stock_members(
            mods_archive, stock, tuple(allowed), game_root=game_root
        )
    except InstallError as error:
        return Result.fail(str(error), code="diagnostics.fix.restore_failed")

    names = ", ".join(Path(item).name for item in allowed)
    return Result.ok(
        f"Made {outcome.changed} vehicle stream member(s) safe "
        f"({outcome.restored} restored, {outcome.removed} removed for fallthrough) "
        f"in mods/{constants.VEHICLE_STREAM_ARCHIVE}: {names}"
    )
