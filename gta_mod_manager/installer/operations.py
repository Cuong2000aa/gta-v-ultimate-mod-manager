"""Executors for the individual actions an install plan can contain."""

from __future__ import annotations

from gta_mod_manager.core.exceptions import InstallError
from gta_mod_manager.core.logging_setup import get_logger
from gta_mod_manager.installer.transaction import JournalEntry, Transaction
from gta_mod_manager.models.enums import FileAction
from gta_mod_manager.models.install_plan import FileOperation
from gta_mod_manager.models.mod_package import InstalledFileRecord
from gta_mod_manager.plugins.gta_v.addon_peds import import_addon_peds, ped_meta_member
from gta_mod_manager.plugins.gta_v.rpf_archive import append_dlclist_entries, import_members
from gta_mod_manager.utils import fs, hashing

_LOGGER = get_logger("installer.operations")


class OperationExecutor:
    """Applies one :class:`FileOperation` and journals what it did."""

    def execute(
        self, operation: FileOperation, transaction: Transaction
    ) -> InstalledFileRecord | None:
        """Perform ``operation``.

        Args:
            operation: The step to apply.
            transaction: Journal that records the step for rollback.

        Returns:
            A record of the written file, or ``None`` for directory creations.

        Raises:
            InstallError: When the operation cannot be performed.
        """
        handler = {
            FileAction.CREATE_DIRECTORY: self._create_directory,
            FileAction.COPY: self._copy,
            FileAction.OVERWRITE: self._copy,
            FileAction.DELETE: self._delete,
            FileAction.RPF_COPY: self._rpf_copy,
            FileAction.RPF_IMPORT: self._rpf_import,
            FileAction.RPF_DLC_REGISTER: self._rpf_dlc_register,
            FileAction.RPF_PED_IMPORT: self._rpf_ped_import,
        }.get(operation.action)

        if handler is None:
            raise InstallError(
                "Unsupported operation in plan",
                action=operation.action.value,
                target=str(operation.target_path),
            )
        return handler(operation, transaction)

    @staticmethod
    def _create_directory(
        operation: FileOperation, transaction: Transaction
    ) -> InstalledFileRecord | None:
        """Create a directory, journalling it only when it was new."""
        if operation.target_path.is_dir():
            return None
        fs.ensure_directory(operation.target_path)
        transaction.record(
            JournalEntry(action=FileAction.CREATE_DIRECTORY, target=operation.target_path)
        )
        _LOGGER.debug("Created directory %s", operation.target_path)
        return None

    @staticmethod
    def _copy(operation: FileOperation, transaction: Transaction) -> InstalledFileRecord:
        """Copy a file, stashing anything it replaces.

        Raises:
            InstallError: When the source is missing or the copy fails.
        """
        source = operation.source_path
        if source is None or not source.is_file():
            raise InstallError(
                "The source file of this operation is missing",
                target=str(operation.target_path),
                source=str(source),
            )

        stashed = transaction.stash_existing(operation.target_path)
        try:
            fs.copy_file(source, operation.target_path)
        except OSError as error:
            raise InstallError(
                "Could not copy a file into the game folder",
                source=str(source),
                target=str(operation.target_path),
                detail=str(error),
            ) from error

        transaction.record(
            JournalEntry(
                action=operation.action,
                target=operation.target_path,
                replaced_backup=stashed,
            )
        )
        return InstalledFileRecord(
            target_path=operation.target_path,
            sha256=hashing.sha256_file(operation.target_path),
            replaced_existing=stashed is not None,
        )

    @staticmethod
    def _rpf_copy(operation: FileOperation, transaction: Transaction) -> InstalledFileRecord:
        """Copy an original archive into the mods folder (large-file safe)."""
        record = OperationExecutor._copy(operation, transaction)
        return InstalledFileRecord(
            target_path=record.target_path,
            sha256=record.sha256,
            replaced_existing=record.replaced_existing,
            shared_archive=True,
            archive_members=record.archive_members,
        )

    @staticmethod
    def _rpf_import(
        operation: FileOperation, transaction: Transaction
    ) -> InstalledFileRecord:
        """Import members into a mods-folder archive, stashing once for rollback."""
        if not operation.archive_members:
            raise InstallError(
                "RPF import has no members",
                target=str(operation.target_path),
            )
        if not operation.target_path.is_file():
            raise InstallError(
                "The mods-folder archive to edit does not exist",
                target=str(operation.target_path),
            )

        stashed = transaction.stash_existing(operation.target_path)
        try:
            import_members(operation.target_path, operation.archive_members)
        except InstallError:
            if stashed is not None and stashed.is_file():
                fs.copy_file(stashed, operation.target_path)
            raise
        except Exception as error:  # noqa: BLE001
            if stashed is not None and stashed.is_file():
                fs.copy_file(stashed, operation.target_path)
            raise InstallError(
                "Could not import files into the mods-folder archive",
                target=str(operation.target_path),
                detail=str(error),
            ) from error

        transaction.record(
            JournalEntry(
                action=FileAction.RPF_IMPORT,
                target=operation.target_path,
                replaced_backup=stashed,
            )
        )
        return InstalledFileRecord(
            target_path=operation.target_path,
            sha256=hashing.sha256_file(operation.target_path),
            replaced_existing=True,
            shared_archive=True,
            archive_members=tuple(member.member_path for member in operation.archive_members),
        )

    @staticmethod
    def _rpf_dlc_register(
        operation: FileOperation, transaction: Transaction
    ) -> InstalledFileRecord:
        """Append DLC pack names to ``dlclist.xml`` inside mods ``update.rpf``."""
        pack_names = tuple(
            line.strip()
            for line in (operation.payload or "").splitlines()
            if line.strip()
        )
        if not pack_names:
            raise InstallError(
                "DLC registration has no pack names",
                target=str(operation.target_path),
            )
        if not operation.target_path.is_file():
            raise InstallError(
                "The mods update.rpf to edit does not exist",
                target=str(operation.target_path),
            )

        stashed = transaction.stash_existing(operation.target_path)
        try:
            append_dlclist_entries(operation.target_path, pack_names)
        except InstallError:
            if stashed is not None and stashed.is_file():
                fs.copy_file(stashed, operation.target_path)
            raise
        except Exception as error:  # noqa: BLE001
            if stashed is not None and stashed.is_file():
                fs.copy_file(stashed, operation.target_path)
            raise InstallError(
                "Could not register DLC packs in dlclist.xml",
                target=str(operation.target_path),
                detail=str(error),
            ) from error

        transaction.record(
            JournalEntry(
                action=FileAction.RPF_DLC_REGISTER,
                target=operation.target_path,
                replaced_backup=stashed,
            )
        )
        return InstalledFileRecord(
            target_path=operation.target_path,
            sha256=hashing.sha256_file(operation.target_path),
            replaced_existing=True,
            shared_archive=True,
            # Track which packs this mod registered so uninstall can reverse them.
            archive_members=tuple(f"dlclist:{name}" for name in pack_names),
        )

    @staticmethod
    def _rpf_ped_import(
        operation: FileOperation, transaction: Transaction
    ) -> InstalledFileRecord:
        """Create/update the manager add-on ped pack with the planned models."""
        if not operation.archive_members:
            raise InstallError(
                "Ped import has no archive members",
                target=str(operation.target_path),
            )

        stashed = (
            transaction.stash_existing(operation.target_path)
            if operation.target_path.is_file()
            else None
        )
        try:
            stems = import_addon_peds(operation.target_path, operation.archive_members)
        except InstallError:
            if stashed is not None and stashed.is_file():
                fs.copy_file(stashed, operation.target_path)
            raise
        except Exception as error:  # noqa: BLE001
            if stashed is not None and stashed.is_file():
                fs.copy_file(stashed, operation.target_path)
            raise InstallError(
                "Could not import character models into the add-on ped pack",
                target=str(operation.target_path),
                detail=str(error),
            ) from error

        tracked = tuple(member.member_path for member in operation.archive_members) + tuple(
            ped_meta_member(stem) for stem in stems
        )
        transaction.record(
            JournalEntry(
                action=FileAction.RPF_PED_IMPORT,
                target=operation.target_path,
                replaced_backup=stashed,
            )
        )
        return InstalledFileRecord(
            target_path=operation.target_path,
            sha256=hashing.sha256_file(operation.target_path),
            replaced_existing=stashed is not None,
            shared_archive=True,
            archive_members=tracked,
        )

    @staticmethod
    def _delete(
        operation: FileOperation, transaction: Transaction
    ) -> InstalledFileRecord | None:
        """Delete a file, stashing it so the step can be undone."""
        stashed = transaction.stash_existing(operation.target_path)
        if not fs.delete_file(operation.target_path):
            return None
        transaction.record(
            JournalEntry(
                action=FileAction.DELETE,
                target=operation.target_path,
                replaced_backup=stashed,
            )
        )
        return None
