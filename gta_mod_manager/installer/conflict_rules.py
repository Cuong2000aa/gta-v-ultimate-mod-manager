"""Individual conflict rules, each answering one "is this a clash?" question."""

from __future__ import annotations

from collections.abc import Iterable
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from gta_mod_manager.core import constants
from gta_mod_manager.installer.vehicle_keys import (
    model_keys_for_installed_mod,
    model_keys_from_archive_members,
)
from gta_mod_manager.models.conflict import Conflict
from gta_mod_manager.models.enums import ConflictSeverity, ConflictType, FileAction
from gta_mod_manager.models.game_install import GameInstall
from gta_mod_manager.models.install_plan import FileOperation, InstallPlan
from gta_mod_manager.models.mod_package import InstalledMod, ModPackage
from gta_mod_manager.utils import fs


@dataclass(frozen=True, slots=True)
class ConflictContext:
    """Everything a conflict rule may inspect.

    Attributes:
        plan: The plan about to be applied.
        install: Target installation.
        package: The analysed package, when available.
        installed: Mods already tracked for this installation.
    """

    plan: InstallPlan
    install: GameInstall
    package: ModPackage | None = None
    installed: tuple[InstalledMod, ...] = ()

    def owner_of(self, target: Path) -> InstalledMod | None:
        """Return the tracked mod that owns ``target``, if any."""
        needle = str(fs.normalise(target)).lower()
        for mod in self.installed:
            for record in mod.installed_files:
                if str(fs.normalise(record.target_path)).lower() == needle:
                    return mod
        return None


class ConflictRule(ABC):
    """One conflict heuristic."""

    #: Stable identifier used in logs.
    rule_id: str = "conflict"

    @abstractmethod
    def evaluate(self, context: ConflictContext) -> Iterable[Conflict]:
        """Return the conflicts this rule detects."""


class FileOverwriteRule(ConflictRule):
    """Reports files the plan would overwrite, naming the owning mod."""

    rule_id = "conflict.file_overwrite"

    def evaluate(self, context: ConflictContext) -> Iterable[Conflict]:
        """Return one conflict per overwritten file or colliding RPF member."""
        conflicts: list[Conflict] = []
        for operation in context.plan.operations:
            if operation.action is FileAction.OVERWRITE:
                owner = context.owner_of(operation.target_path)
                conflicts.append(
                    Conflict(
                        conflict_type=ConflictType.FILE_OVERWRITE,
                        severity=ConflictSeverity.WARNING,
                        key=operation.target_path.name,
                        description=(
                            f"{operation.target_path.name} already exists and will be replaced"
                            + (f" (installed by {owner.display_name})" if owner else "")
                        ),
                        paths=(operation.target_path,),
                        owner=owner.display_name if owner else None,
                        resolution_hint="A backup is created automatically; use Undo to revert",
                    )
                )
            elif operation.action is FileAction.RPF_IMPORT:
                conflicts.extend(self._archive_member_conflicts(context, operation))
        return tuple(conflicts)

    @staticmethod
    def _archive_member_conflicts(
        context: ConflictContext, operation: FileOperation
    ) -> tuple[Conflict, ...]:
        """Block when another mod already replaced the same stock vehicle files."""
        claimed: dict[str, str] = {}
        for mod in context.installed:
            for record in mod.installed_files:
                if not record.shared_archive:
                    continue
                if fs.normalise(record.target_path) != fs.normalise(operation.target_path):
                    continue
                for member in record.archive_members:
                    claimed[member.lower()] = mod.display_name

        conflicts: list[Conflict] = []
        seen_keys: set[str] = set()
        for member in operation.archive_members:
            owner = claimed.get(member.member_path.lower())
            if owner is None:
                continue
            keys = model_keys_from_archive_members((member.member_path,))
            key = next(iter(keys), member.member_path.rsplit("/", 1)[-1].lower())
            if key in seen_keys:
                continue
            seen_keys.add(key)
            conflicts.append(
                Conflict(
                    conflict_type=ConflictType.DUPLICATE_VEHICLE_NAME,
                    severity=ConflictSeverity.BLOCKING,
                    key=key,
                    description=(
                        f"Spawn/model '{key}' inside {operation.target_path.name} was already "
                        f"replaced by {owner}"
                    ),
                    paths=(operation.target_path,),
                    owner=owner,
                    resolution_hint="Uninstall the other replace mod first, or choose another vehicle",
                )
            )
        return tuple(conflicts)


class ProtectedTargetRule(ConflictRule):
    """Reports any attempt to write an original game file as blocking."""

    rule_id = "conflict.protected"

    def evaluate(self, context: ConflictContext) -> Iterable[Conflict]:
        """Return blocking conflicts for protected destinations."""
        mods_root = context.install.mods_path
        conflicts: list[Conflict] = []
        for operation in context.plan.operations:
            name = operation.target_path.name.lower()
            inside_mods = fs.is_relative_to(operation.target_path, mods_root)
            if name in constants.PROTECTED_ROOT_FILES and not inside_mods:
                conflicts.append(
                    Conflict(
                        conflict_type=ConflictType.PROTECTED_TARGET,
                        severity=ConflictSeverity.BLOCKING,
                        key=name,
                        description=f"{name} is an original game file and is never modified",
                        paths=(operation.target_path,),
                        resolution_hint="Install this file inside the mods folder instead",
                    )
                )
        return tuple(conflicts)


class DuplicateVehicleRule(ConflictRule):
    """Reports spawn codes / replace models already claimed by another mod."""

    rule_id = "conflict.duplicate_vehicle"

    def evaluate(self, context: ConflictContext) -> Iterable[Conflict]:
        """Return one conflict per colliding spawn code or replace model."""
        incoming = self._incoming_keys(context)
        if not incoming:
            return ()

        conflicts: list[Conflict] = []
        for mod in context.installed:
            if mod.mod_id == context.plan.package_id:
                continue
            members = [
                member
                for record in mod.installed_files
                for member in record.archive_members
            ]
            claimed = model_keys_for_installed_mod(mod.spawn_codes, members)
            for code in sorted(incoming.intersection(claimed)):
                conflicts.append(
                    Conflict(
                        conflict_type=ConflictType.DUPLICATE_VEHICLE_NAME,
                        severity=ConflictSeverity.BLOCKING,
                        key=code,
                        description=(
                            f"Spawn code '{code}' is already used by {mod.display_name}. "
                            "Two replace mods cannot own the same stock vehicle."
                        ),
                        owner=mod.display_name,
                        resolution_hint="Uninstall the other mod, or pick a different replace target",
                    )
                )
        return tuple(conflicts)

    @staticmethod
    def _incoming_keys(context: ConflictContext) -> set[str]:
        """Spawn codes from meta plus model keys from planned RPF imports."""
        keys: set[str] = set()
        if context.package is not None:
            keys.update(
                code.strip().lower()
                for code in context.package.vehicles.spawn_codes
                if code and code.strip()
            )
        for operation in context.plan.operations:
            if operation.action is not FileAction.RPF_IMPORT:
                continue
            keys.update(
                model_keys_from_archive_members(
                    member.member_path for member in operation.archive_members
                )
            )
        return keys


class DuplicateHandlingRule(ConflictRule):
    """Reports handling ids that two mods would both define."""

    rule_id = "conflict.duplicate_handling"

    def evaluate(self, context: ConflictContext) -> Iterable[Conflict]:
        """Return one conflict per duplicated handling id inside the package."""
        if context.package is None:
            return ()
        seen: dict[str, int] = {}
        for entry in context.package.vehicles.handling:
            seen[entry.handling_id] = seen.get(entry.handling_id, 0) + 1
        return tuple(
            Conflict(
                conflict_type=ConflictType.DUPLICATE_HANDLING_ID,
                severity=ConflictSeverity.WARNING,
                key=handling_id,
                description=f"handling.meta declares '{handling_id}' {count} times",
                resolution_hint="Remove the duplicate entry from handling.meta",
            )
            for handling_id, count in sorted(seen.items())
            if count > 1
        )


class DuplicateDlcRule(ConflictRule):
    """Reports add-on DLC pack names already present in the installation."""

    rule_id = "conflict.duplicate_dlc"

    def evaluate(self, context: ConflictContext) -> Iterable[Conflict]:
        """Return one conflict per colliding DLC pack name."""
        if context.package is None:
            return ()
        conflicts: list[Conflict] = []
        dlc_root = context.install.dlc_packs_path

        for pack in context.package.vehicles.dlc_packs:
            existing = dlc_root / pack.pack_name
            owner = context.owner_of(existing / "dlc.rpf") if existing.is_dir() else None
            is_reinstall = owner is not None and owner.mod_id == context.plan.package_id
            if existing.is_dir() and not is_reinstall:
                conflicts.append(
                    Conflict(
                        conflict_type=ConflictType.DUPLICATE_DLC,
                        severity=ConflictSeverity.BLOCKING,
                        key=pack.pack_name,
                        description=f"A DLC pack named '{pack.pack_name}' is already "
                        "installed",
                        paths=(existing,),
                        owner=owner.display_name if owner else None,
                        resolution_hint="Uninstall the existing pack or rename this one",
                    )
                )
            for mod in context.installed:
                if pack.pack_name in mod.dlc_packs and mod.mod_id != context.plan.package_id:
                    conflicts.append(
                        Conflict(
                            conflict_type=ConflictType.DUPLICATE_DLC,
                            severity=ConflictSeverity.BLOCKING,
                            key=pack.pack_name,
                            description=f"{mod.display_name} already registers the DLC pack "
                            f"'{pack.pack_name}'",
                            owner=mod.display_name,
                        )
                    )
        return tuple(conflicts)


class DuplicateGameConfigRule(ConflictRule):
    """Reports a second ``gameconfig.xml``, which always breaks the game."""

    rule_id = "conflict.duplicate_gameconfig"

    def evaluate(self, context: ConflictContext) -> Iterable[Conflict]:
        """Return a blocking conflict when another gameconfig mod is present."""
        touches_gameconfig = any(
            operation.target_path.name.lower() == constants.GAMECONFIG_XML
            for operation in context.plan.operations
        )
        if not touches_gameconfig:
            return ()

        owners = [
            mod
            for mod in context.installed
            if mod.mod_id != context.plan.package_id
            and any(
                record.target_path.name.lower() == constants.GAMECONFIG_XML
                for record in mod.installed_files
            )
        ]
        if not owners:
            return ()
        return tuple(
            Conflict(
                conflict_type=ConflictType.DUPLICATE_GAMECONFIG,
                severity=ConflictSeverity.BLOCKING,
                key=constants.GAMECONFIG_XML,
                description=f"{mod.display_name} already installs a custom gameconfig.xml",
                owner=mod.display_name,
                resolution_hint="Only one gameconfig mod can be active at a time",
            )
            for mod in owners
        )


class DuplicateTextureRule(ConflictRule):
    """Reports texture dictionaries that appear twice inside one package."""

    rule_id = "conflict.duplicate_texture"

    def evaluate(self, context: ConflictContext) -> Iterable[Conflict]:
        """Return one conflict per duplicated ``.ytd`` name."""
        if context.package is None:
            return ()
        counts: dict[str, list[Path]] = {}
        for file in context.package.inventory.by_suffix(".ytd", ".ydr"):
            counts.setdefault(file.lower_name, []).append(file.absolute_path)
        return tuple(
            Conflict(
                conflict_type=ConflictType.DUPLICATE_TEXTURE,
                severity=ConflictSeverity.INFO,
                key=name,
                description=f"The package contains {len(paths)} copies of {name}",
                paths=tuple(paths),
                resolution_hint="Only the last copy processed would survive; "
                "check which variant you want",
            )
            for name, paths in sorted(counts.items())
            if len(paths) > 1
        )


class DuplicatePackfileRule(ConflictRule):
    """Reports two operations writing to the same destination."""

    rule_id = "conflict.duplicate_packfile"

    def evaluate(self, context: ConflictContext) -> Iterable[Conflict]:
        """Return one conflict per destination targeted more than once."""
        counts: dict[str, list[Path]] = {}
        for operation in context.plan.operations:
            if operation.action is FileAction.CREATE_DIRECTORY:
                continue
            key = str(fs.normalise(operation.target_path)).lower()
            counts.setdefault(key, []).append(operation.target_path)
        return tuple(
            Conflict(
                conflict_type=ConflictType.DUPLICATE_PACKFILE,
                severity=ConflictSeverity.WARNING,
                key=paths[0].name,
                description=f"{len(paths)} files of this package target {paths[0].name}",
                paths=tuple(paths),
                resolution_hint="The package likely ships several variants of the same file",
            )
            for paths in counts.values()
            if len(paths) > 1
        )


class MissingDependencyRule(ConflictRule):
    """Turns unmet dependencies recorded on the plan into conflicts."""

    rule_id = "conflict.missing_dependency"

    def evaluate(self, context: ConflictContext) -> Iterable[Conflict]:
        """Return a warning per dependency warning attached to the plan."""
        return tuple(
            Conflict(
                conflict_type=ConflictType.MISSING_DEPENDENCY,
                severity=ConflictSeverity.WARNING,
                key=warning,
                description=warning,
                resolution_hint="Install the missing component before launching the game",
            )
            for warning in context.plan.dependency_warnings
        )


def default_conflict_rules() -> tuple[ConflictRule, ...]:
    """Return every conflict rule the application runs."""
    return (
        ProtectedTargetRule(),
        DuplicateVehicleRule(),
        DuplicateDlcRule(),
        DuplicateGameConfigRule(),
        DuplicateHandlingRule(),
        DuplicateTextureRule(),
        DuplicatePackfileRule(),
        FileOverwriteRule(),
        MissingDependencyRule(),
    )
