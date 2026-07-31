"""Use-cases around the library of installed mods."""

from __future__ import annotations

import shutil
from dataclasses import dataclass, replace
from pathlib import Path

from gta_mod_manager.core.app_paths import AppPaths
from gta_mod_manager.core.events import (
    EventBus,
    ModLibraryChangedEvent,
    NotificationEvent,
    NotificationLevel,
    new_operation_id,
)
from gta_mod_manager.core.exceptions import InstallError, UninstallError
from gta_mod_manager.core.logging_setup import get_logger
from gta_mod_manager.core.progress import NullProgressReporter
from gta_mod_manager.core.protocols import ProgressReporter
from gta_mod_manager.core.result import Result
from gta_mod_manager.installer.uninstaller import Uninstaller, UninstallOutcome
from gta_mod_manager.models.backup_snapshot import OperationRecord
from gta_mod_manager.models.enums import ModStatus, OperationKind, OperationStatus
from gta_mod_manager.models.game_install import GameInstall
from gta_mod_manager.models.install_plan import ArchiveMemberImport
from gta_mod_manager.models.mod_package import InstalledFileRecord, InstalledMod
from gta_mod_manager.plugins.gta_v.addon_peds import (
    PED_META_MEMBER_PREFIX,
    import_addon_peds,
    remove_addon_peds,
)
from gta_mod_manager.plugins.gta_v.rpf_archive import (
    append_dlclist_entries,
    import_members,
    remove_dlclist_entries,
    restore_stock_members,
    stock_archive_for_mods_copy,
)
from gta_mod_manager.repository.backup_repository import JsonBackupRepository
from gta_mod_manager.repository.mod_repository import JsonModRepository
from gta_mod_manager.services.backup_service import BackupService
from gta_mod_manager.utils import fs

_LOGGER = get_logger("services.library")
_DISABLED_QUARANTINE = "disabled-mods"
_RPF_MEMBER_CACHE = "rpf-members"


@dataclass(frozen=True, slots=True)
class ModSummary:
    """An installed mod reduced to what the list view displays."""

    mod: InstalledMod
    size_label: str
    is_intact: bool

    @property
    def mod_id(self) -> str:
        """Return the mod identifier."""
        return self.mod.mod_id

    @property
    def display_name(self) -> str:
        """Return the mod name."""
        return self.mod.display_name


class LibraryService:
    """Lists, verifies, disables and removes installed mods."""

    def __init__(
        self,
        mods: JsonModRepository,
        uninstaller: Uninstaller,
        backups: BackupService,
        backup_repository: JsonBackupRepository,
        bus: EventBus,
        paths: AppPaths,
    ) -> None:
        self._mods = mods
        self._uninstaller = uninstaller
        self._backups = backups
        self._backup_repository = backup_repository
        self._bus = bus
        self._paths = paths

    def list_installed(self, install: GameInstall | None = None) -> tuple[ModSummary, ...]:
        """Return the installed mods, optionally filtered by installation."""
        records = (
            self._mods.list_for_game(install.root_path)
            if install is not None
            else self._mods.list_all()
        )
        return tuple(self._summarise(record) for record in records)

    def get(self, mod_id: str) -> InstalledMod | None:
        """Return one installed mod, or ``None`` when unknown."""
        return self._mods.get(mod_id)

    def search(
        self, query: str, install: GameInstall | None = None
    ) -> tuple[ModSummary, ...]:
        """Return installed mods whose name, kind or spawn code matches ``query``."""
        needle = query.strip().lower()
        if not needle:
            return self.list_installed(install)
        return tuple(
            summary
            for summary in self.list_installed(install)
            if needle in summary.display_name.lower()
            or needle in summary.mod.kind.lower()
            or any(needle in code for code in summary.mod.spawn_codes)
        )

    def uninstall(
        self,
        mod_id: str,
        *,
        force: bool = False,
        backup_first: bool = True,
        reporter: ProgressReporter | None = None,
    ) -> Result[int]:
        """Remove a mod, snapshotting its files first.

        Returns:
            The number of files that were deleted.
        """
        mod = self._mods.get(mod_id)
        if mod is None:
            return Result.fail("This mod is not tracked by the library", code="library.unknown")

        operation_id = new_operation_id()
        record = OperationRecord(
            operation_id=operation_id,
            kind=OperationKind.UNINSTALL,
            status=OperationStatus.RUNNING,
            description=f"Uninstall {mod.display_name}",
            mod_id=mod_id,
        )
        self._backup_repository.add_operation(record)

        # Shared archives are multi-gigabyte mods copies of an .rpf. Never
        # snapshot them again on uninstall: either restore stock members (when
        # other mods still share the file) or restore the install-time backup.
        shared_files = [item for item in mod.installed_files if item.shared_archive]
        plain_files = [item for item in mod.installed_files if not item.shared_archive]
        will_back_up = bool(backup_first and plain_files)
        total_steps = 1 + int(will_back_up) + int(bool(shared_files))

        reporter = reporter or NullProgressReporter()
        reporter.start(operation_id, f"Removing {mod.display_name}", total=total_steps)
        step = 0

        if will_back_up:
            reporter.advance(
                operation_id, step, f"Backing up {mod.display_name} before removal"
            )
            snapshot = self._backups.snapshot_paths(
                game_root=mod.game_root,
                paths=tuple(item.target_path for item in plain_files),
                reason=f"Before uninstalling {mod.display_name}",
                mod_id=mod_id,
                reporter=reporter,
            )
            record = replace(record, snapshot_id=snapshot.snapshot_id)
            step += 1

        members_restored = 0
        if shared_files:
            reporter.advance(
                operation_id, step, "Restoring stock models in the shared archive"
            )
        try:
            shared_warnings, members_restored, archives_restored = (
                self._restore_shared_archives(mod, reporter)
            )
        except InstallError as error:
            reporter.finish(operation_id, f"Could not remove {mod.display_name}")
            self._backup_repository.add_operation(
                record.completed(OperationStatus.FAILED, str(error))
            )
            return Result.fail(str(error), code="library.uninstall_failed")
        if shared_files:
            step += 1

        removable = replace(mod, installed_files=tuple(plain_files))

        reporter.advance(operation_id, step, "Deleting the files this mod installed")
        try:
            if removable.installed_files:
                outcome = self._uninstaller.uninstall(
                    removable, force=force, reporter=reporter
                )
            else:
                outcome = UninstallOutcome()
        except UninstallError as error:
            reporter.finish(operation_id, f"Could not remove {mod.display_name}")
            self._backup_repository.add_operation(
                record.completed(OperationStatus.FAILED, str(error))
            )
            return Result.fail(str(error), code="library.uninstall_failed")

        reporter.finish(operation_id, f"Removed {mod.display_name}")
        self._clear_quarantine(mod_id)
        self._clear_member_payloads(mod_id)
        self._mods.remove(mod_id)
        self._backup_repository.add_operation(record.completed(OperationStatus.SUCCEEDED))
        self._bus.publish(ModLibraryChangedEvent(reason="uninstalled"))

        warnings: list[str] = list(shared_warnings)
        removed_count = len(outcome.removed) + members_restored + archives_restored
        if outcome.modified_externally:
            warnings.append(
                f"{len(outcome.modified_externally)} file(s) were changed after installation "
                "and were left in place"
            )
            self._bus.publish(
                NotificationEvent(
                    title=f"{mod.display_name} removed with warnings",
                    message=warnings[0],
                    level=NotificationLevel.WARNING,
                )
            )
        else:
            detail = f"{len(outcome.removed)} file(s) deleted"
            if members_restored:
                detail = (
                    f"restored {members_restored} stock model(s) in the shared archive"
                    + (f"; {detail}" if outcome.removed else "")
                )
            self._bus.publish(
                NotificationEvent(
                    title=f"{mod.display_name} removed",
                    message=detail,
                    level=NotificationLevel.SUCCESS,
                )
            )
        return Result(value=removed_count, warnings=tuple(warnings))

    def _restore_shared_archives(
        self, mod: InstalledMod, reporter: ProgressReporter | None = None
    ) -> tuple[tuple[str, ...], int, int]:
        """Undo this mod's edits to shared mods ``.rpf`` archives.

        The edits are always reverted at the *member* level: the mod's DLC
        ``dlclist`` entries, its add-on ped models and its replaced stream
        members are removed / restored from the original game archive. This is
        backup-independent, so it works even though shared archives are no
        longer full-copied into a snapshot at install time.

        The install-time backup, when it exists (older installs), is used only
        as a last resort for records that carry no actionable members.

        Returns:
            ``(warnings, members_restored, archives_restored)``.
        """
        shared = [item for item in mod.installed_files if item.shared_archive]
        if not shared:
            return (), 0, 0

        warnings: list[str] = []
        others = [
            other
            for other in self._mods.list_for_game(mod.game_root)
            if other.mod_id != mod.mod_id
        ]
        members_restored = 0
        backup_only_paths: list[Path] = []
        for record in shared:
            owners = sorted(
                {
                    other.display_name
                    for other in others
                    for owned in other.installed_files
                    if owned.shared_archive
                    and fs.normalise(owned.target_path)
                    == fs.normalise(record.target_path)
                }
            )
            restored, note = self._revert_shared_members(record, mod, owners)
            members_restored += restored
            if note:
                warnings.append(note)
            elif restored == 0:
                # Nothing member-level to undo; may need the legacy full backup.
                backup_only_paths.append(record.target_path)

        if not backup_only_paths:
            return tuple(warnings), members_restored, 0

        archives_restored, backup_warnings = self._restore_from_install_backup(
            mod, backup_only_paths, reporter
        )
        warnings.extend(backup_warnings)
        return tuple(warnings), members_restored, archives_restored

    def _revert_shared_members(
        self, record: InstalledFileRecord, mod: InstalledMod, owners: list[str]
    ) -> tuple[int, str]:
        """Remove this mod's members from one shared archive.

        Returns ``(members_restored, warning)``. ``warning`` is empty when
        nothing needed saying.
        """
        dlc_packs = tuple(
            member[len("dlclist:") :]
            for member in record.archive_members
            if member.startswith("dlclist:")
        )
        ped_stems = tuple(
            member[len(PED_META_MEMBER_PREFIX) :]
            for member in record.archive_members
            if member.startswith(PED_META_MEMBER_PREFIX)
        )
        stock_members = tuple(
            member
            for member in record.archive_members
            if not member.startswith("dlclist:")
            and not member.startswith(PED_META_MEMBER_PREFIX)
        )
        shared_suffix = (
            f"; archive still used by {', '.join(owners)}" if owners else ""
        )

        restored = 0
        details: list[str] = []
        if dlc_packs:
            removed = remove_dlclist_entries(record.target_path, dlc_packs)
            restored += removed
            details.append(f"removed {removed} DLC entry(ies) from dlclist.xml")
        if ped_stems:
            removed = remove_addon_peds(record.target_path, ped_stems)
            restored += removed
            details.append(f"removed {removed} add-on ped model(s)")
        if stock_members:
            stock = stock_archive_for_mods_copy(record.target_path, mod.game_root)
            outcome = restore_stock_members(
                record.target_path,
                stock,
                stock_members,
                game_root=mod.game_root,
            )
            restored += outcome.changed
            details.append(
                f"restored {outcome.restored}, removed {outcome.removed} "
                f"(OpenIV fallthrough)"
            )

        if not details:
            return 0, ""
        note = f"{'; '.join(details)} in {record.target_path.name}{shared_suffix}"
        return restored, note

    def _restore_from_install_backup(
        self,
        mod: InstalledMod,
        paths: list[Path],
        reporter: ProgressReporter | None,
    ) -> tuple[int, list[str]]:
        """Legacy fallback: restore whole archives from the install snapshot."""
        if not mod.backup_id:
            return 0, [
                "Shared archive(s) had nothing to undo at the member level and no "
                "install backup exists; left in place."
            ]
        snapshot = self._backup_repository.get_snapshot(mod.backup_id)
        if snapshot is None:
            return 0, ["Install backup for shared archive(s) is missing; left in place"]

        wanted = {fs.normalise(path) for path in paths}
        restored_archives = 0
        for entry in snapshot.entries:
            if fs.normalise(entry.original_path) not in wanted:
                continue
            self._backups.restore(replace(snapshot, entries=(entry,)), reporter)
            restored_archives += 1
        if restored_archives:
            _LOGGER.info(
                "Restored %d shared archive(s) from backup for uninstall of %s",
                restored_archives,
                mod.display_name,
            )
        return restored_archives, []

    def verify(self, mod_id: str) -> Result[tuple[str, ...]]:
        """Return the files of ``mod_id`` that are missing or were changed."""
        mod = self._mods.get(mod_id)
        if mod is None:
            return Result.fail("This mod is not tracked by the library", code="library.unknown")

        problems: list[str] = []
        if mod.status is ModStatus.DISABLED:
            for record in mod.installed_files:
                if record.shared_archive:
                    continue
                if not self._is_under_game(mod.game_root, record.target_path):
                    # OpenIV staging / external payloads are not loadable in-game.
                    continue
                quarantined = self._quarantine_file_path(mod, record.target_path)
                if quarantined.is_file():
                    if record.sha256 and not self._matches(quarantined, record.sha256):
                        problems.append(f"changed in quarantine: {record.target_path}")
                elif record.target_path.exists():
                    if record.sha256 and not self._matches(record.target_path, record.sha256):
                        problems.append(f"changed: {record.target_path}")
                else:
                    problems.append(f"missing from quarantine: {record.target_path}")
            return Result.ok(tuple(problems))

        for record in mod.installed_files:
            if not record.target_path.exists():
                problems.append(f"missing: {record.target_path}")
            elif record.sha256 and not self._matches(record.target_path, record.sha256):
                problems.append(f"changed: {record.target_path}")

        status = ModStatus.BROKEN if problems else ModStatus.INSTALLED
        if mod.status is not status:
            self._mods.update_status(mod_id, status)
            self._bus.publish(ModLibraryChangedEvent(reason="verified"))
        return Result.ok(tuple(problems))

    def set_enabled(
        self,
        mod_id: str,
        enabled: bool,
        *,
        reporter: ProgressReporter | None = None,
    ) -> Result[InstalledMod]:
        """Physically enable or disable a mod by quarantining its loose files.

        Disable moves non-shared files under the app backup folder and reverts
        shared ``.rpf`` members. Enable restores quarantined files and re-imports
        cached shared-archive payloads when available.
        """
        mod = self._mods.get(mod_id)
        if mod is None:
            return Result.fail("This mod is not tracked by the library", code="library.unknown")

        reporter = reporter or NullProgressReporter()
        operation_id = new_operation_id()
        if enabled:
            if mod.status is ModStatus.INSTALLED:
                return Result.ok(mod)
            return self._physically_enable(mod, operation_id, reporter)
        if mod.status is ModStatus.DISABLED:
            return Result.ok(mod)
        return self._physically_disable(mod, operation_id, reporter)

    def _physically_disable(
        self,
        mod: InstalledMod,
        operation_id: str,
        reporter: ProgressReporter,
    ) -> Result[InstalledMod]:
        plain = [item for item in mod.installed_files if not item.shared_archive]
        shared = [item for item in mod.installed_files if item.shared_archive]
        total = 1 + int(bool(plain)) + int(bool(shared))
        reporter.start(operation_id, f"Disabling {mod.display_name}", total=total)
        step = 0
        warnings: list[str] = []

        try:
            if plain:
                reporter.advance(operation_id, step, "Moving loose files out of the game folder")
                moved = self._quarantine_plain_files(mod, plain)
                step += 1
                _LOGGER.info("Quarantined %d file(s) for %s", moved, mod.display_name)
            if shared:
                reporter.advance(
                    operation_id, step, "Restoring stock models in shared archives"
                )
                shared_warnings, _members, _archives = self._restore_shared_archives(
                    mod, reporter
                )
                warnings.extend(shared_warnings)
                if any(item.member_payloads for item in shared):
                    warnings.append(
                        "Shared archive models were restored to stock. "
                        "Enable will re-apply the cached payloads."
                    )
                else:
                    warnings.append(
                        "Shared archive models were restored to stock. "
                        "This install has no cached payloads — reinstall after enabling."
                    )
                step += 1
            reporter.advance(operation_id, step, "Updating library status")
            updated = self._mods.update_status(mod.mod_id, ModStatus.DISABLED)
            if updated is None:
                raise InstallError("Could not update mod status")
        except (OSError, InstallError, ValueError) as error:
            reporter.finish(operation_id, f"Could not disable {mod.display_name}")
            return Result.fail(str(error), code="library.disable_failed")

        reporter.finish(operation_id, f"Disabled {mod.display_name}")
        self._bus.publish(ModLibraryChangedEvent(reason="status"))
        unique_warnings = tuple(dict.fromkeys(warnings))
        self._bus.publish(
            NotificationEvent(
                title=f"{mod.display_name} disabled",
                message="Loose files were moved out of the game folder.",
                level=NotificationLevel.SUCCESS,
            )
        )
        return Result(value=updated, warnings=unique_warnings)

    def _physically_enable(
        self,
        mod: InstalledMod,
        operation_id: str,
        reporter: ProgressReporter,
    ) -> Result[InstalledMod]:
        plain = [item for item in mod.installed_files if not item.shared_archive]
        has_shared = any(item.shared_archive for item in mod.installed_files)
        total = 2 + int(has_shared)
        reporter.start(operation_id, f"Enabling {mod.display_name}", total=total)
        warnings: list[str] = []
        try:
            reporter.advance(operation_id, 0, "Restoring loose files into the game folder")
            restored = self._restore_plain_files(mod, plain)
            step = 1
            if has_shared:
                reporter.advance(operation_id, step, "Re-applying shared archive models")
                warnings.extend(self._reapply_shared_archives(mod))
                step += 1
            reporter.advance(operation_id, step, "Updating library status")
            updated = self._mods.update_status(mod.mod_id, ModStatus.INSTALLED)
            if updated is None:
                raise InstallError("Could not update mod status")
        except (OSError, InstallError, ValueError) as error:
            reporter.finish(operation_id, f"Could not enable {mod.display_name}")
            return Result.fail(str(error), code="library.enable_failed")

        reporter.finish(
            operation_id,
            f"Enabled {mod.display_name} ({restored} file(s) restored)",
        )
        self._bus.publish(ModLibraryChangedEvent(reason="status"))
        self._bus.publish(
            NotificationEvent(
                title=f"{mod.display_name} enabled",
                message=f"Restored {restored} file(s) into the game folder.",
                level=NotificationLevel.SUCCESS,
            )
        )
        return Result(value=updated, warnings=tuple(dict.fromkeys(warnings)))

    def _reapply_shared_archives(self, mod: InstalledMod) -> tuple[str, ...]:
        """Re-import this mod's cached shared-archive edits after a physical enable."""
        warnings: list[str] = []
        for record in mod.installed_files:
            if not record.shared_archive:
                continue
            dlc_packs = tuple(
                member[len("dlclist:") :]
                for member in record.archive_members
                if member.startswith("dlclist:")
            )
            if dlc_packs:
                if not record.target_path.is_file():
                    warnings.append(
                        f"Cannot re-register DLC packs — missing {record.target_path.name}"
                    )
                else:
                    appended = append_dlclist_entries(record.target_path, dlc_packs)
                    _LOGGER.info(
                        "Re-registered %d DLC pack(s) for %s", appended, mod.display_name
                    )

            if not record.member_payloads:
                stock_members = tuple(
                    member
                    for member in record.archive_members
                    if not member.startswith("dlclist:")
                    and not member.startswith(PED_META_MEMBER_PREFIX)
                )
                if stock_members:
                    warnings.append(
                        f"No cached payloads for {record.target_path.name}; "
                        "reinstall the mod to restore shared archive models."
                    )
                continue

            imports: list[ArchiveMemberImport] = []
            for payload in record.member_payloads:
                source = self._paths.library / payload.library_relative
                if not source.is_file():
                    warnings.append(f"Missing cached payload: {payload.member_path}")
                    continue
                imports.append(
                    ArchiveMemberImport(
                        source_path=source, member_path=payload.member_path
                    )
                )
            if not imports:
                continue
            if not record.target_path.is_file() and "umm_peds" not in str(
                record.target_path
            ).lower():
                warnings.append(
                    f"Cannot re-import into missing archive {record.target_path.name}"
                )
                continue

            is_ped = any(
                member.startswith(PED_META_MEMBER_PREFIX)
                for member in record.archive_members
            ) or "umm_peds" in str(record.target_path).lower()
            try:
                if is_ped:
                    import_addon_peds(record.target_path, imports)
                else:
                    import_members(record.target_path, tuple(imports))
            except Exception as error:  # noqa: BLE001 - surface as enable warning
                warnings.append(
                    f"Could not re-apply shared archive content in "
                    f"{record.target_path.name}: {error}"
                )
        return tuple(warnings)

    def _quarantine_plain_files(
        self, mod: InstalledMod, records: list[InstalledFileRecord]
    ) -> int:
        moved = 0
        for record in records:
            source = fs.normalise(record.target_path)
            if not self._is_under_game(mod.game_root, source):
                # Staging / OpenIV payloads live under the app library, not the
                # game folder — leaving them alone is enough for a soft disable.
                continue
            if not source.exists():
                continue
            destination = self._quarantine_file_path(mod, source)
            if destination.exists():
                fs.delete_file(destination) if destination.is_file() else shutil.rmtree(
                    destination
                )
            if source.is_dir():
                fs.ensure_directory(destination.parent)
                shutil.move(str(source), str(destination))
            else:
                fs.move_file(source, destination)
            moved += 1
        return moved

    def _restore_plain_files(
        self, mod: InstalledMod, records: list[InstalledFileRecord]
    ) -> int:
        restored = 0
        for record in records:
            destination = fs.normalise(record.target_path)
            if not self._is_under_game(mod.game_root, destination):
                continue
            source = self._quarantine_file_path(mod, destination)
            if not source.exists():
                if destination.exists():
                    continue
                raise InstallError(
                    f"Quarantined file missing for {destination.name}; "
                    "reinstall the mod to restore it."
                )
            if destination.exists():
                if destination.is_dir():
                    shutil.rmtree(destination)
                else:
                    fs.delete_file(destination)
            if source.is_dir():
                fs.ensure_directory(destination.parent)
                shutil.move(str(source), str(destination))
            else:
                fs.move_file(source, destination)
            restored += 1
        quarantine = self._quarantine_root(mod.mod_id)
        if quarantine.is_dir() and not any(quarantine.rglob("*")):
            shutil.rmtree(quarantine, ignore_errors=True)
        elif quarantine.is_dir():
            # Remove empty parents left after restores.
            for path in sorted(quarantine.rglob("*"), reverse=True):
                if path.is_dir():
                    try:
                        path.rmdir()
                    except OSError:
                        pass
            try:
                quarantine.rmdir()
            except OSError:
                pass
        return restored

    def _quarantine_root(self, mod_id: str) -> Path:
        safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in mod_id)
        return self._paths.backup / _DISABLED_QUARANTINE / (safe or "mod")

    def _quarantine_file_path(self, mod: InstalledMod, target: Path) -> Path:
        relative = self._relative_to_game(mod.game_root, target)
        return self._quarantine_root(mod.mod_id) / relative

    def _clear_quarantine(self, mod_id: str) -> None:
        quarantine = self._quarantine_root(mod_id)
        if quarantine.exists():
            shutil.rmtree(quarantine, ignore_errors=True)

    def _clear_member_payloads(self, mod_id: str) -> None:
        safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in mod_id)
        cache = self._paths.library / _RPF_MEMBER_CACHE / (safe or "mod")
        if cache.exists():
            shutil.rmtree(cache, ignore_errors=True)

    @staticmethod
    def _is_under_game(game_root: Path, target: Path) -> bool:
        root = fs.normalise(game_root)
        absolute = fs.normalise(target)
        try:
            relative = absolute.relative_to(root)
        except ValueError:
            return False
        return not relative.is_absolute() and ".." not in relative.parts

    @staticmethod
    def _relative_to_game(game_root: Path, target: Path) -> Path:
        root = fs.normalise(game_root)
        absolute = fs.normalise(target)
        try:
            relative = absolute.relative_to(root)
        except ValueError as error:
            raise ValueError(f"Refusing path outside game root: {target}") from error
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"Refusing unsafe relative path: {relative}")
        return relative

    def _summarise(self, mod: InstalledMod) -> ModSummary:
        """Build the list-view summary of ``mod``."""
        total = 0
        intact = True
        for record in mod.installed_files:
            if record.shared_archive:
                if record.target_path.is_file():
                    continue
                intact = False
                continue
            live = record.target_path
            candidate = live
            if (
                mod.status is ModStatus.DISABLED
                and self._is_under_game(mod.game_root, live)
            ):
                quarantined = self._quarantine_file_path(mod, live)
                if quarantined.exists():
                    candidate = quarantined
            if candidate.is_file():
                total += candidate.stat().st_size
            elif candidate.is_dir():
                continue
            else:
                intact = False
        return ModSummary(mod=mod, size_label=fs.human_size(total), is_intact=intact)

    @staticmethod
    def _matches(path: Path, expected: str) -> bool:
        """Return whether the file content still matches ``expected``."""
        from gta_mod_manager.utils import hashing

        try:
            return hashing.sha256_file(path) == expected
        except OSError:
            return False
