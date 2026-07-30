"""The install plan: an explicit, reviewable list of file operations."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from gta_mod_manager.models.conflict import ConflictReport
from gta_mod_manager.models.enums import FileAction, InstallTarget


@dataclass(frozen=True, slots=True)
class ArchiveMemberImport:
    """One file to insert into a mods-folder ``.rpf`` archive.

    Attributes:
        source_path: Absolute path of the payload on disk.
        member_path: Path inside the outer archive, using ``/`` separators.
            Nested archives are expressed as a ``.rpf`` segment, e.g.
            ``levels/gta5/vehicles.rpf/gauntlet.yft``.
    """

    source_path: Path
    member_path: str


@dataclass(frozen=True, slots=True)
class FileOperation:
    """One atomic change the installer will perform.

    Attributes:
        action: What will happen to :attr:`target_path`.
        target_path: Absolute destination inside the game installation.
            For archive imports this is the mods-folder ``.rpf`` file itself,
            never a path that descends into the archive.
        source_path: Absolute source inside the extraction workspace.
        target_kind: Which safety zone the target belongs to.
        payload: Text payload for XML operations.
        description: Line shown in the preview table.
        archive_members: Members to import when ``action`` is ``RPF_IMPORT``.
    """

    action: FileAction
    target_path: Path
    source_path: Path | None = None
    target_kind: InstallTarget = InstallTarget.MODS_FOLDER
    payload: str | None = None
    description: str = ""
    archive_members: tuple[ArchiveMemberImport, ...] = ()

    @property
    def is_mutating_existing(self) -> bool:
        """Return whether the operation changes something already on disk."""
        return self.action in (
            FileAction.OVERWRITE,
            FileAction.DELETE,
            FileAction.XML_PATCH,
            FileAction.XML_APPEND,
            FileAction.RPF_IMPORT,
            FileAction.RPF_DLC_REGISTER,
            FileAction.RPF_PED_IMPORT,
        )

    @property
    def size_bytes(self) -> int:
        """Return the size of the source payload(s), or ``0`` when not applicable."""
        if self.action is FileAction.RPF_IMPORT or self.action is FileAction.RPF_PED_IMPORT:
            total = 0
            for member in self.archive_members:
                if member.source_path.is_file():
                    total += member.source_path.stat().st_size
            return total
        if self.source_path is None or not self.source_path.is_file():
            return 0
        return self.source_path.stat().st_size


@dataclass(frozen=True, slots=True)
class ManualStep:
    """An action the user must perform because the manager refuses to do it.

    The absolute safety rule forbids writing inside *original* ``.rpf``
    archives. Mods-folder copies may be edited (vehicle replace, dlclist).
    When a change still cannot be mapped automatically, the plan carries an
    explicit instruction instead of silently skipping it.

    Attributes:
        title: One line summary shown in the preview dialog.
        instruction: Step by step description for the user.
        payload_path: Files staged outside the game for the user to import.
        target_hint: The in-game location the user should import them into.
    """

    title: str
    instruction: str
    payload_path: Path | None = None
    target_hint: str | None = None


@dataclass(frozen=True, slots=True)
class InstallPlan:
    """Everything the installer needs to install one package safely.

    A plan is *data*: it can be rendered in the preview dialog, validated,
    diffed against the current game state and executed transactionally.
    """

    plan_id: str
    package_id: str
    display_name: str
    game_root: Path
    operations: tuple[FileOperation, ...] = field(default_factory=tuple)
    conflicts: ConflictReport = field(default_factory=ConflictReport)
    dependency_warnings: tuple[str, ...] = field(default_factory=tuple)
    notes: tuple[str, ...] = field(default_factory=tuple)
    manual_steps: tuple[ManualStep, ...] = field(default_factory=tuple)
    requires_openiv: bool = False

    @property
    def is_empty(self) -> bool:
        """Return whether the plan would change nothing."""
        return not self.operations

    @property
    def affected_paths(self) -> tuple[Path, ...]:
        """Return every existing target path that the plan will modify."""
        seen: dict[Path, None] = {}
        for operation in self.operations:
            if operation.is_mutating_existing or operation.target_path.exists():
                seen.setdefault(operation.target_path, None)
        return tuple(seen)

    @property
    def created_directories(self) -> tuple[Path, ...]:
        """Return the directories the plan will create."""
        return tuple(
            operation.target_path
            for operation in self.operations
            if operation.action is FileAction.CREATE_DIRECTORY
        )

    @property
    def total_bytes(self) -> int:
        """Return the amount of data the plan will copy."""
        return sum(operation.size_bytes for operation in self.operations)

    @property
    def root_operations(self) -> tuple[FileOperation, ...]:
        """Return operations writing outside the ``mods`` folder."""
        return tuple(
            operation
            for operation in self.operations
            if operation.target_kind is not InstallTarget.MODS_FOLDER
        )

    def with_conflicts(self, report: ConflictReport) -> InstallPlan:
        """Return a copy of the plan carrying a conflict report."""
        return InstallPlan(
            plan_id=self.plan_id,
            package_id=self.package_id,
            display_name=self.display_name,
            game_root=self.game_root,
            operations=self.operations,
            conflicts=report,
            dependency_warnings=self.dependency_warnings,
            notes=self.notes,
            manual_steps=self.manual_steps,
            requires_openiv=self.requires_openiv,
        )
