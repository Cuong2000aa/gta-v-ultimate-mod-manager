"""Safe edits to mods-folder copies of GTA V ``.rpf`` archives.

Original game archives are never opened for writing. Callers copy an archive
into ``<game>/mods/`` first, then this module replaces nested members and
saves the copy with OPEN encryption so OpenIV.asi can load it.

Stock ``x64e.rpf`` is NG-encrypted. fivefury can read NG but cannot write it.
Nested ``vehicles.rpf`` also stores resource bodies *without* RSC7 headers
(flags live on the RPF entry). fivefury's writer then invents flags from the
compressed size and raises ``block_count is too large to encode into RSC7
flags`` for large vanilla assets. Before saving we materialise every loaded
resource as a full RSC7 blob using the entry's existing flags.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
import re
from xml.etree import ElementTree

from fivefury import RpfArchive
from fivefury.crypto import NONE_ENCRYPTION, OPEN_ENCRYPTION, ensure_game_crypto
from fivefury.rpf.entries import RpfResourceFileEntry
from fivefury.rpf.utils import _build_rsc7, _is_rsc7, _resource_version_from_flags

from gta_mod_manager.core import constants
from gta_mod_manager.core.exceptions import InstallError
from gta_mod_manager.core.logging_setup import get_logger
from gta_mod_manager.models.install_plan import ArchiveMemberImport
from gta_mod_manager.utils import fs
from gta_mod_manager.utils.xml_tools import parse_xml_text

_LOGGER = get_logger("plugins.gta_v.rpf")

_WRITABLE_ENCRYPTION = frozenset({NONE_ENCRYPTION, OPEN_ENCRYPTION})
_DLC_VEHICLE_NESTED_PATHS = (
    "x64/levels/gta5/vehicles.rpf",
    "x64/levels/gta5/vehicles/vehicles.rpf",
    "x64/levels/gta5/vehicles/mpbusinessvehicles.rpf",
    "x64/levels/gta5/vehicles/mpbusiness2vehicles.rpf",
)

#: DLC packs that commonly host replaceable story-mode cars (read-only stock lookup).
_COMMON_VEHICLE_DLC_PACKS = (
    "mpbusiness",
    "mpbusiness2",
    "mpluxe",
    "mpluxe2",
    "mpchristmas2",
    "mppilot",
)


@dataclass(frozen=True, slots=True)
class StockMemberSource:
    """Location of a vanilla member that can restore a mods-archive import."""

    archive_path: Path
    nested_path: str | None
    leaf: str


@dataclass(frozen=True, slots=True)
class RestoreMembersResult:
    """Outcome of restoring or removing imported shared-archive members."""

    restored: int = 0
    removed: int = 0
    sources: tuple[StockMemberSource, ...] = ()

    @property
    def changed(self) -> int:
        """Return the number of members made safe."""
        return self.restored + self.removed


def split_member_path(member_path: str) -> tuple[str | None, str]:
    """Split ``levels/gta5/vehicles.rpf/foo.yft`` into nested archive + leaf.

    Returns:
        ``(nested_rpf_path, leaf_name)``. When the member lives in the outer
        archive itself, ``nested_rpf_path`` is ``None``.
    """
    normalised = member_path.replace("\\", "/").strip("/")
    if not normalised:
        raise InstallError("Archive member path is empty")
    parts = normalised.split("/")
    for index, part in enumerate(parts[:-1]):
        if part.lower().endswith(".rpf"):
            nested = "/".join(parts[: index + 1])
            leaf = "/".join(parts[index + 1 :])
            if not leaf:
                raise InstallError(
                    "Archive member path ends at a nested .rpf with no file",
                    member_path=member_path,
                )
            return nested, leaf
    return None, normalised


def force_open_encryption(archive: RpfArchive) -> bool:
    """Force OPEN encryption on ``archive`` and every loaded nested child.

    Returns:
        ``True`` when at least one archive's encryption mode was changed.
    """
    changed = False
    stack: list[RpfArchive] = [archive]
    seen: set[int] = set()
    while stack:
        current = stack.pop()
        identity = id(current)
        if identity in seen:
            continue
        seen.add(identity)
        if current.encryption not in _WRITABLE_ENCRYPTION:
            _LOGGER.info(
                "Converting %s from encryption %s to OPEN for mods-folder write",
                current.name or "archive",
                current.encryption,
            )
            changed = True
        current.encryption = OPEN_ENCRYPTION
        for entry in current.iter_entries():
            child = getattr(entry, "child_archive", None)
            if child is not None:
                stack.append(child)
        for child in getattr(current, "children", ()) or ():
            stack.append(child)
    return changed


def materialize_resources_for_write(archive: RpfArchive) -> int:
    """Attach full RSC7 blobs to every loaded resource entry.

    Stock nested archives often store only the compressed resource body; the
    system/graphics flags sit on the RPF entry. fivefury's writer expects a
    complete RSC7 file (or a small uncompressed payload). Rebuilding with the
    entry's existing flags keeps large vanilla assets writable.

    Returns:
        The number of entries that had to be rebuilt from logical payloads.
    """
    rebuilt = 0
    stack: list[RpfArchive] = [archive]
    seen: set[int] = set()
    while stack:
        current = stack.pop()
        identity = id(current)
        if identity in seen:
            continue
        seen.add(identity)

        for entry in list(current.iter_entries()):
            child = getattr(entry, "child_archive", None)
            if child is not None:
                stack.append(child)
            if not isinstance(entry, RpfResourceFileEntry):
                continue

            existing = getattr(entry, "_data", None)
            if existing is not None and _is_rsc7(bytes(existing)):
                continue

            try:
                raw = current.read_entry_raw(entry)
            except Exception as error:  # noqa: BLE001
                raise InstallError(
                    "Could not read a resource entry while preparing the mods archive",
                    entry=entry.name,
                    detail=str(error),
                ) from error

            if _is_rsc7(raw):
                entry._data = raw
                continue

            try:
                logical = current.read_entry_bytes(entry)
                version = _resource_version_from_flags(
                    entry.system_flags.value, entry.graphics_flags.value
                )
                entry._data = _build_rsc7(
                    logical,
                    version=version,
                    sys_flags=entry.system_flags.value,
                    gfx_flags=entry.graphics_flags.value,
                )
            except Exception as error:  # noqa: BLE001
                raise InstallError(
                    "Could not rebuild a resource entry for the mods archive write",
                    entry=entry.name,
                    detail=str(error),
                ) from error
            rebuilt += 1

        for child in getattr(current, "children", ()) or ():
            stack.append(child)

    if rebuilt:
        _LOGGER.info(
            "Rebuilt %d resource entr(y/ies) into full RSC7 blobs for writing",
            rebuilt,
        )
    return rebuilt


def import_members(archive_path: Path, members: tuple[ArchiveMemberImport, ...]) -> None:
    """Replace members inside the mods-folder archive at ``archive_path``.

    The archive is rewritten atomically by fivefury (temp file + replace) and
    forced to OPEN encryption so the write path is supported.

    Args:
        archive_path: Absolute path of the mods-folder ``.rpf`` copy.
        members: Source files and their destinations inside the archive.

    Raises:
        InstallError: When the archive or a source file cannot be used.
    """
    if not members:
        return
    if not archive_path.is_file():
        raise InstallError(
            "The mods-folder archive to edit does not exist yet",
            target=str(archive_path),
        )

    # NG table decryption keys the archive *file name*; keep names like x64e.rpf.
    ensure_game_crypto()

    grouped: dict[str | None, list[tuple[str, Path]]] = defaultdict(list)
    for member in members:
        if not member.source_path.is_file():
            raise InstallError(
                "An archive import source file is missing",
                source=str(member.source_path),
                member_path=member.member_path,
            )
        nested, leaf = split_member_path(member.member_path)
        grouped[nested].append((leaf, member.source_path))

    try:
        with RpfArchive.from_path(str(archive_path)) as archive:
            for nested_path, payloads in grouped.items():
                target_archive = archive
                if nested_path is not None:
                    entry = archive.find_entry(nested_path)
                    if entry is None:
                        raise InstallError(
                            "Nested archive was not found inside the mods copy",
                            archive=str(archive_path),
                            nested=nested_path,
                        )
                    loaded = archive.load_nested_archive(entry)
                    if loaded is None:
                        raise InstallError(
                            "Nested archive could not be loaded from the mods copy",
                            archive=str(archive_path),
                            nested=nested_path,
                        )
                    target_archive = loaded
                for leaf, source in payloads:
                    target_archive.add(leaf, source.read_bytes())
                    _LOGGER.debug(
                        "Queued %s -> %s/%s",
                        source.name,
                        nested_path or archive_path.name,
                        leaf,
                    )
            # Prepare every loaded resource, then flip encryption, then save.
            materialize_resources_for_write(archive)
            force_open_encryption(archive)
            _save_mods_archive(archive, archive_path)
    except InstallError:
        raise
    except Exception as error:  # noqa: BLE001 - surface as install failure
        raise InstallError(
            "Could not update the mods-folder archive",
            target=str(archive_path),
            detail=str(error),
        ) from error

    _LOGGER.info(
        "Imported %d member(s) into mods archive %s",
        len(members),
        archive_path.name,
    )


def stock_archive_for_mods_copy(mods_archive: Path, game_root: Path) -> Path:
    """Map ``<game>/mods/.../file.rpf`` back to the untouched game archive."""
    mods_root = (game_root / constants.MODS_FOLDER_NAME).resolve()
    resolved = mods_archive.resolve()
    try:
        relative = resolved.relative_to(mods_root)
    except ValueError as error:
        raise InstallError(
            "Shared archive is not under the game mods folder",
            archive=str(mods_archive),
            game_root=str(game_root),
        ) from error
    return game_root / relative


def resolve_stock_members(
    stock_archive: Path,
    game_root: Path,
    member_paths: tuple[str, ...],
    *,
    mirrored_only: bool = False,
) -> dict[str, StockMemberSource]:
    """Resolve vanilla members across the mirrored archive and vehicle DLC archives.

    The mirrored archive is authoritative when it contains the member. If it
    does not, patchday archives are searched newest-first because later packs
    override earlier vanilla assets. Common root vehicle archives are a final
    read-only lookup tier.

    Args:
        mirrored_only: When ``True``, only inspect ``stock_archive`` (fast).
    """
    requested = tuple(
        dict.fromkeys(path.replace("\\", "/").strip("/") for path in member_paths if path)
    )
    unresolved = set(requested)
    resolved: dict[str, StockMemberSource] = {}
    if not unresolved:
        return resolved

    ensure_game_crypto()
    candidates = (
        (stock_archive,)
        if mirrored_only
        else _stock_archive_candidates(stock_archive, game_root)
    )
    for candidate in candidates:
        if not unresolved:
            break
        if not candidate.is_file():
            continue
        try:
            with RpfArchive.from_path(str(candidate)) as archive:
                nested_cache: dict[str | None, RpfArchive | None] = {None: archive}
                for member_path in tuple(unresolved):
                    requested_nested, leaf = split_member_path(member_path)
                    search_paths = _stock_nested_candidates(requested_nested)
                    for nested_path in search_paths:
                        if nested_path not in nested_cache:
                            nested_cache[nested_path] = _try_load_target_archive(
                                archive, nested_path
                            )
                        target = nested_cache[nested_path]
                        if target is None or _find_leaf_entry(target, leaf) is None:
                            continue
                        resolved[member_path] = StockMemberSource(
                            archive_path=candidate,
                            nested_path=nested_path,
                            leaf=leaf,
                        )
                        unresolved.remove(member_path)
                        break
        except Exception as error:  # noqa: BLE001 - skip unreadable optional candidates
            _LOGGER.warning("Could not inspect stock candidate %s: %s", candidate, error)

    return resolved


def resolve_stock_member(
    stock_archive: Path,
    game_root: Path,
    member_path: str,
) -> StockMemberSource | None:
    """Return the vanilla source for one member, if GTA's archives contain it."""
    normalised = member_path.replace("\\", "/").strip("/")
    return resolve_stock_members(stock_archive, game_root, (normalised,)).get(normalised)


def restore_stock_members(
    mods_archive: Path,
    stock_archive: Path,
    member_paths: tuple[str, ...],
    *,
    game_root: Path | None = None,
) -> RestoreMembersResult:
    """Restore imported members, or remove unsafe overrides as a fallback.

    Used when uninstalling one replace mod while other mods still share the
    same ``mods/*.rpf``.

    Strategy (restore-safe, never hard-fails on missing mirrored stock):

    1. Prefer restoring bytes from the mirrored stock archive when the leaf
       exists there (base-game vehicles in ``x64e.rpf``).
    2. If mirrored stock lacks the leaf, search patchday / other game archives
       for the same leaf and restore from there when found.
    3. Last resort: delete the member from the mods copy. OpenIV.asi then falls
       through to vanilla DLC — correct for patchday cars wrongly imported into
       ``mods/x64e.rpf`` (e.g. ``huntley``).

    Returns:
        Counts and sources for restored/deleted members.
    """
    unique = tuple(dict.fromkeys(path.replace("\\", "/").strip("/") for path in member_paths if path))
    if not unique:
        return RestoreMembersResult()
    if not mods_archive.is_file():
        raise InstallError(
            "The mods-folder archive to edit does not exist",
            target=str(mods_archive),
        )
    root = game_root or stock_archive.parent
    if not stock_archive.is_file() and not root.is_dir():
        raise InstallError(
            "No original game archives are available to restore stock files",
            source=str(stock_archive),
        )

    # Fast path for uninstall: restore from the mirrored stock archive when the
    # leaf exists there. Anything else (patchday cars wrongly placed in mods
    # x64e, e.g. huntley) is deleted so OpenIV.asi falls through to vanilla DLC.
    # Full alternate-archive search remains available via resolve_stock_members
    # for install validation; scanning every patchday here would hang uninstall.
    sources = resolve_stock_members(
        stock_archive, root, unique, mirrored_only=True
    )

    payloads: dict[str, bytes] = {}
    unreadable: set[str] = set()
    for member_path, source in sources.items():
        try:
            payloads[member_path] = _read_stock_member(source)
        except InstallError as error:
            _LOGGER.warning(
                "Could not read resolved stock for %s (%s); will delete from mods instead",
                member_path,
                error,
            )
            unreadable.add(member_path)
    for member_path in unreadable:
        sources.pop(member_path, None)

    restored = 0
    removed = 0
    used_sources: list[StockMemberSource] = []
    try:
        with RpfArchive.from_path(str(mods_archive)) as mods:
            for member_path in unique:
                nested_path, leaf = split_member_path(member_path)
                mods_target = _load_target_archive(mods, mods_archive, nested_path)
                source = sources.get(member_path)
                payload = payloads.get(member_path)
                if source is not None and payload is not None:
                    mods_target.add(leaf, payload)
                    restored += 1
                    used_sources.append(source)
                    _LOGGER.info(
                        "Restored %s from vanilla source %s/%s",
                        leaf,
                        source.archive_path,
                        source.nested_path or "",
                    )
                    continue

                entry = _find_leaf_entry(mods_target, leaf)
                if entry is not None and entry.parent is not None:
                    entry.parent.files.remove(entry)
                    mods_target._invalidate_index()
                    removed += 1
                    _LOGGER.warning(
                        "No restorable vanilla payload for %s; removed it from %s "
                        "so OpenIV.asi falls through to original game archives",
                        member_path,
                        mods_archive,
                    )
                else:
                    _LOGGER.info(
                        "Member %s already absent from mods archive; nothing to undo",
                        member_path,
                    )
            # Entries we just wrote are already full RSC7 with stock flags.
            # Still materialise any other loaded resources that lack headers
            # before the OPEN rewrite.
            materialize_resources_for_write(mods)
            force_open_encryption(mods)
            _save_mods_archive(mods, mods_archive)
    except InstallError:
        raise
    except Exception as error:  # noqa: BLE001
        raise InstallError(
            "Could not restore stock members into the mods-folder archive",
            target=str(mods_archive),
            detail=str(error),
        ) from error

    _LOGGER.info(
        "Made %d member(s) safe in %s (%d restored, %d removed for fallback)",
        restored + removed,
        mods_archive.name,
        restored,
        removed,
    )
    return RestoreMembersResult(
        restored=restored,
        removed=removed,
        sources=tuple(used_sources),
    )


def _stock_archive_candidates(stock_archive: Path, game_root: Path) -> tuple[Path, ...]:
    """Return read-only vanilla archive candidates in restore priority order."""
    candidates: list[Path] = []
    if stock_archive.is_file():
        candidates.append(stock_archive)

    dlcpacks = game_root / "update" / "x64" / "dlcpacks"
    if dlcpacks.is_dir():
        patchdays = [
            path / "dlc.rpf"
            for path in dlcpacks.glob("patchday*")
            if (path / "dlc.rpf").is_file()
        ]
        candidates.extend(sorted(patchdays, key=_patchday_sort_key, reverse=True))
        for pack_name in _COMMON_VEHICLE_DLC_PACKS:
            candidate = dlcpacks / pack_name / "dlc.rpf"
            if candidate.is_file():
                candidates.append(candidate)

    for name in ("x64e.rpf", "x64w.rpf", "x64i.rpf"):
        candidate = game_root / name
        if candidate.is_file():
            candidates.append(candidate)

    deduplicated: dict[str, Path] = {}
    for candidate in candidates:
        deduplicated.setdefault(str(candidate.resolve()).lower(), candidate)
    return tuple(deduplicated.values())


def _patchday_sort_key(path: Path) -> tuple[int, int, str]:
    """Sort patchday packs by generation, preferring enhanced variants."""
    name = path.parent.name.lower()
    match = re.search(r"patchday(\d+)", name)
    generation = int(match.group(1)) if match else 0
    enhanced = int("g9ec" in name)
    return generation, enhanced, name


def _stock_nested_candidates(requested: str | None) -> tuple[str | None, ...]:
    """Return likely nested vehicle archives without duplicating paths."""
    values: list[str | None] = [requested]
    lowered = (requested or "").lower()
    if requested is not None and (
        lowered.endswith("vehicles.rpf") or "/vehiclemods/" in lowered
    ):
        values.extend(_DLC_VEHICLE_NESTED_PATHS)
    elif requested is None:
        values.extend(_DLC_VEHICLE_NESTED_PATHS)
    return tuple(dict.fromkeys(values))


def _try_load_target_archive(
    archive: RpfArchive, nested_path: str | None
) -> RpfArchive | None:
    """Load an optional nested archive without treating absence as an error."""
    if nested_path is None:
        return archive
    entry = archive.find_entry(nested_path)
    if entry is None:
        return None
    return archive.load_nested_archive(entry)


def _read_stock_member(source: StockMemberSource) -> bytes:
    """Read a stock member as a standalone payload preserving resource flags."""
    with RpfArchive.from_path(str(source.archive_path)) as archive:
        target = _load_target_archive(archive, source.archive_path, source.nested_path)
        entry = _find_leaf_entry(target, source.leaf)
        if entry is None:  # pragma: no cover - archive changed between resolve/read
            raise InstallError(
                "Resolved stock member disappeared before it could be restored",
                archive=str(source.archive_path),
                member=source.leaf,
            )
        return target.read_entry_standalone(entry)


def _save_mods_archive(archive: RpfArchive, archive_path: Path) -> None:
    """Persist ``archive`` to ``archive_path``, clearing read-only first.

    fivefury saves via temp + ``os.replace``. On Windows that needs delete
    rights on the destination; when replace is denied (game still running,
    Explorer preview, AV), fall back to a sibling ``.fixed`` file the user
    can swap in after closing the game.
    """
    fs.make_writable(archive_path)
    try:
        archive.save(str(archive_path))
        return
    except OSError as error:
        fallback = archive_path.with_name(archive_path.name + ".fixed")
        _LOGGER.warning(
            "Atomic save of %s failed (%s); writing %s instead",
            archive_path.name,
            error,
            fallback.name,
        )
        try:
            archive.save(str(fallback))
        except Exception as nested:  # noqa: BLE001
            raise InstallError(
                "Could not save the mods-folder archive",
                target=str(archive_path),
                detail=str(error),
            ) from nested
        # Prefer swapping the fallback into place when possible.
        try:
            fs.make_writable(archive_path)
            fallback.replace(archive_path)
        except OSError:
            raise InstallError(
                "Could not replace the mods-folder archive (is GTA V still open?). "
                f"A repaired file was written to {fallback.name} — close the game, "
                f"delete {archive_path.name}, and rename {fallback.name} to {archive_path.name}.",
                target=str(archive_path),
                fallback=str(fallback),
                detail=str(error),
            ) from error


def append_dlclist_entries(mods_archive: Path, pack_names: Sequence[str]) -> int:
    """Ensure each ``dlcpacks:/{name}/`` item exists in mods ``dlclist.xml``.

    Returns the number of entries newly added.
    """
    from gta_mod_manager.core.constants import DLC_LIST_MEMBER

    names = [n.strip().strip("/") for n in pack_names if n and n.strip()]
    if not names:
        return 0
    if not mods_archive.is_file():
        raise InstallError(
            "Mods update.rpf is missing; copy the stock archive first",
            archive=str(mods_archive),
        )
    ensure_game_crypto()
    try:
        with RpfArchive.from_path(str(mods_archive)) as archive:
            entry = archive.find_entry(DLC_LIST_MEMBER)
            if entry is None:
                entry = _find_leaf_entry(archive, "dlclist.xml")
            if entry is None:
                raise InstallError(
                    "dlclist.xml was not found inside update.rpf",
                    archive=str(mods_archive),
                    member=DLC_LIST_MEMBER,
                )
            raw = archive.read_entry_bytes(entry, logical=True)
            text = raw.decode("utf-8", errors="replace")
            result = parse_xml_text(text, source=mods_archive / DLC_LIST_MEMBER)
            added = _merge_dlclist_items(result.root, names)
            if added == 0:
                return 0
            new_bytes = _serialize_xml_bytes(result.root)
            member_path = getattr(entry, "path", None) or DLC_LIST_MEMBER
            archive.add(member_path.replace("\\", "/"), new_bytes)
            # Real update.rpf carries headerless resource bodies; rebuild them
            # with their stock flags or the writer invents bad RSC7 flags.
            materialize_resources_for_write(archive)
            force_open_encryption(archive)
            _save_mods_archive(archive, mods_archive)
    except InstallError:
        raise
    except Exception as error:  # noqa: BLE001
        raise InstallError(
            "Could not update dlclist.xml inside mods update.rpf",
            archive=str(mods_archive),
            detail=str(error),
        ) from error

    _LOGGER.info(
        "Registered %d DLC pack(s) in %s",
        added,
        mods_archive.name,
    )
    return added


def remove_dlclist_entries(mods_archive: Path, pack_names: Sequence[str]) -> int:
    """Remove ``dlcpacks:/{name}/`` items for ``pack_names`` from mods ``dlclist.xml``.

    Returns the number of entries removed. Leaves other packs untouched.
    """
    from gta_mod_manager.core.constants import DLC_LIST_MEMBER

    names = {n.strip().strip("/").lower() for n in pack_names if n and n.strip()}
    if not names:
        return 0
    if not mods_archive.is_file():
        _LOGGER.warning("Mods update.rpf missing; skip dlclist cleanup (%s)", mods_archive)
        return 0
    ensure_game_crypto()
    try:
        with RpfArchive.from_path(str(mods_archive)) as archive:
            entry = archive.find_entry(DLC_LIST_MEMBER)
            if entry is None:
                entry = _find_leaf_entry(archive, "dlclist.xml")
            if entry is None:
                _LOGGER.warning("dlclist.xml missing in %s; skip cleanup", mods_archive)
                return 0
            raw = archive.read_entry_bytes(entry, logical=True)
            text = raw.decode("utf-8", errors="replace")
            result = parse_xml_text(text, source=mods_archive / DLC_LIST_MEMBER)
            removed = _strip_dlclist_items(result.root, names)
            if removed == 0:
                return 0
            new_bytes = _serialize_xml_bytes(result.root)
            member_path = getattr(entry, "path", None) or DLC_LIST_MEMBER
            archive.add(member_path.replace("\\", "/"), new_bytes)
            materialize_resources_for_write(archive)
            force_open_encryption(archive)
            _save_mods_archive(archive, mods_archive)
    except InstallError:
        raise
    except Exception as error:  # noqa: BLE001
        raise InstallError(
            "Could not remove DLC entries from dlclist.xml",
            archive=str(mods_archive),
            detail=str(error),
        ) from error

    _LOGGER.info(
        "Removed %d DLC pack entry(ies) from %s",
        removed,
        mods_archive.name,
    )
    return removed


def _dlc_item_text(pack_name: str) -> str:
    """Return the canonical ``dlclist.xml`` Item text for ``pack_name``."""
    return f"dlcpacks:/{pack_name.strip().strip('/')}/"


def _merge_dlclist_items(root: ElementTree.Element, pack_names: Sequence[str]) -> int:
    """Append missing pack Item nodes under Paths. Returns count added."""
    paths = root.find("Paths")
    if paths is None:
        paths = ElementTree.SubElement(root, "Paths")
    existing = {
        (item.text or "").strip().rstrip("/").lower()
        for item in paths.findall("Item")
    }
    added = 0
    for name in pack_names:
        text = _dlc_item_text(name)
        key = text.rstrip("/").lower()
        if key in existing:
            continue
        item = ElementTree.SubElement(paths, "Item")
        item.text = text
        existing.add(key)
        added += 1
    return added


def _strip_dlclist_items(root: ElementTree.Element, pack_names_lower: set[str]) -> int:
    """Remove Item nodes whose pack name is in ``pack_names_lower``."""
    paths = root.find("Paths")
    if paths is None:
        return 0
    removed = 0
    for item in list(paths.findall("Item")):
        text = (item.text or "").strip().replace("\\", "/")
        # dlcpacks:/name/ or dlcpacks:\\name\\
        lower = text.lower()
        pack = ""
        for prefix in ("dlcpacks:/", "dlcpacks:\\"):
            if lower.startswith(prefix):
                pack = text[len(prefix) :].strip("/\\").split("/")[0].split("\\")[0]
                break
        if pack.lower() in pack_names_lower:
            paths.remove(item)
            removed += 1
    return removed


def _serialize_xml_bytes(root: ElementTree.Element) -> bytes:
    """Serialize ``root`` to UTF-8 XML bytes with declaration."""
    from gta_mod_manager.utils.xml_tools import _indent

    _indent(root)
    payload = ElementTree.tostring(root, encoding="utf-8", xml_declaration=True)
    return payload if isinstance(payload, bytes) else payload.encode("utf-8")


def _load_target_archive(
    archive: RpfArchive, archive_path: Path, nested_path: str | None
) -> RpfArchive:
    """Return ``archive`` or a loaded nested child for ``nested_path``."""
    if nested_path is None:
        return archive
    entry = archive.find_entry(nested_path)
    if entry is None:
        raise InstallError(
            "Nested archive was not found",
            archive=str(archive_path),
            nested=nested_path,
        )
    loaded = archive.load_nested_archive(entry)
    if loaded is None:
        raise InstallError(
            "Nested archive could not be loaded",
            archive=str(archive_path),
            nested=nested_path,
        )
    return loaded


def _find_leaf_entry(archive: RpfArchive, leaf: str):
    """Locate ``leaf`` inside ``archive`` by file name.

    fivefury's ``find_entry`` is unreliable for bare names inside a nested
    archive, so fall back to a linear scan.
    """
    needle = leaf.replace("\\", "/").rsplit("/", 1)[-1].lower()
    for entry in archive.iter_entries():
        if entry.name.lower() == needle:
            return entry
    return archive.find_entry(leaf)
