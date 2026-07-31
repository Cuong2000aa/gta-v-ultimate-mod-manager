"""Use-case: the conflict center, which audits the whole installation."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from gta_mod_manager.core import constants
from gta_mod_manager.core.logging_setup import get_logger
from gta_mod_manager.installer.vehicle_keys import model_keys_for_installed_mod
from gta_mod_manager.models.conflict import Conflict, ConflictReport
from gta_mod_manager.models.enums import ConflictSeverity, ConflictType, ModStatus
from gta_mod_manager.models.game_install import GameInstall
from gta_mod_manager.models.mod_package import InstalledMod
from gta_mod_manager.repository.mod_repository import JsonModRepository

_LOGGER = get_logger("services.conflicts")


@dataclass(frozen=True, slots=True)
class ConflictGroup:
    """Conflicts of one type, ready to be rendered as a tree section."""

    conflict_type: ConflictType
    conflicts: tuple[Conflict, ...] = field(default_factory=tuple)

    @property
    def title(self) -> str:
        """Return the section heading."""
        return f"{self.conflict_type.display_name} ({len(self.conflicts)})"

    @property
    def worst_severity(self) -> ConflictSeverity:
        """Return the highest severity inside the group."""
        order = (ConflictSeverity.BLOCKING, ConflictSeverity.WARNING, ConflictSeverity.INFO)
        for severity in order:
            if any(item.severity is severity for item in self.conflicts):
                return severity
        return ConflictSeverity.INFO


class ConflictService:
    """Audits an installation for clashes between already installed mods."""

    def __init__(self, mods: JsonModRepository) -> None:
        self._mods = mods

    def audit(self, install: GameInstall) -> ConflictReport:
        """Return every conflict between the mods installed in ``install``."""
        installed = tuple(
            mod
            for mod in self._mods.list_for_game(install.root_path)
            if mod.status is not ModStatus.DISABLED
        )
        conflicts: list[Conflict] = []
        conflicts.extend(self._shared_files(installed))
        conflicts.extend(self._duplicate_replace_vehicles(installed))
        conflicts.extend(self._duplicate_dlc_packs(installed))
        conflicts.extend(self._multiple_gameconfigs(installed))
        conflicts.extend(self._missing_files(installed))

        report = ConflictReport(conflicts=tuple(conflicts))
        _LOGGER.info(
            "Audited %d installed mod(s): %d conflict(s)", len(installed), len(report.conflicts)
        )
        return report

    def grouped(self, install: GameInstall) -> tuple[ConflictGroup, ...]:
        """Return the audit result grouped by conflict type."""
        report = self.audit(install)
        groups = [
            ConflictGroup(conflict_type=conflict_type, conflicts=items)
            for conflict_type, items in report.grouped().items()
        ]
        severity_rank = {
            ConflictSeverity.BLOCKING: 0,
            ConflictSeverity.WARNING: 1,
            ConflictSeverity.INFO: 2,
        }
        groups.sort(key=lambda group: (severity_rank[group.worst_severity], group.title))
        return tuple(groups)

    # ------------------------------------------------------------------
    # Individual audits
    # ------------------------------------------------------------------
    @staticmethod
    def _shared_files(installed: tuple[InstalledMod, ...]) -> tuple[Conflict, ...]:
        """Return non-shared files claimed by more than one installed mod.

        Shared mods-folder archives (``x64e.rpf``) are excluded: many replace
        vehicles intentionally share that file. Collisions inside it are
        reported by :meth:`_duplicate_replace_vehicles` instead.
        """
        owners: dict[str, list[tuple[str, str]]] = defaultdict(list)
        paths: dict[str, Path] = {}
        for mod in installed:
            for record in mod.installed_files:
                if record.shared_archive:
                    continue
                key = str(record.target_path).lower()
                owners[key].append((mod.mod_id, mod.display_name))
                paths[key] = record.target_path
        conflicts: list[Conflict] = []
        for key, entries in sorted(owners.items()):
            ids = tuple(dict.fromkeys(mod_id for mod_id, _ in entries))
            if len(ids) < 2:
                continue
            names = tuple(dict.fromkeys(name for _, name in entries))
            conflicts.append(
                Conflict(
                    conflict_type=ConflictType.FILE_OVERWRITE,
                    severity=ConflictSeverity.WARNING,
                    key=paths[key].name,
                    description=f"{paths[key].name} is claimed by: {', '.join(names)}",
                    paths=(paths[key],),
                    owner=names[0],
                    owner_mod_ids=ids,
                    resolution_hint="Disable one of the conflicting mods",
                )
            )
        return tuple(conflicts)

    @staticmethod
    def _duplicate_replace_vehicles(installed: tuple[InstalledMod, ...]) -> tuple[Conflict, ...]:
        """Block when two mods replace the same stock vehicle / spawn code.

        Keys come from declared spawn codes and from ``.yft`` / ``.ytd`` members
        imported into a shared archive (``buffalo2.yft`` → ``buffalo2``).
        """
        owners: dict[str, list[tuple[str, str]]] = defaultdict(list)
        for mod in installed:
            members = [
                member
                for record in mod.installed_files
                for member in record.archive_members
            ]
            for key in model_keys_for_installed_mod(mod.spawn_codes, members):
                owners[key].append((mod.mod_id, mod.display_name))
        conflicts: list[Conflict] = []
        for code, entries in sorted(owners.items()):
            ids = tuple(dict.fromkeys(mod_id for mod_id, _ in entries))
            if len(ids) < 2:
                continue
            names = tuple(dict.fromkeys(name for _, name in entries))
            conflicts.append(
                Conflict(
                    conflict_type=ConflictType.DUPLICATE_VEHICLE_NAME,
                    severity=ConflictSeverity.BLOCKING,
                    key=code,
                    description=(
                        f"Two or more mods replace spawn '{code}': {', '.join(names)}. "
                        "Only one replace vehicle can own that stock model."
                    ),
                    owner=names[0],
                    owner_mod_ids=ids,
                    resolution_hint="Disable one of the conflicting mods",
                )
            )
        return tuple(conflicts)

    @staticmethod
    def _duplicate_dlc_packs(installed: tuple[InstalledMod, ...]) -> tuple[Conflict, ...]:
        """Return DLC pack names registered by more than one mod."""
        owners: dict[str, list[tuple[str, str]]] = defaultdict(list)
        for mod in installed:
            for pack in mod.dlc_packs:
                owners[pack].append((mod.mod_id, mod.display_name))
        conflicts: list[Conflict] = []
        for pack, entries in sorted(owners.items()):
            ids = tuple(dict.fromkeys(mod_id for mod_id, _ in entries))
            if len(ids) < 2:
                continue
            names = tuple(dict.fromkeys(name for _, name in entries))
            conflicts.append(
                Conflict(
                    conflict_type=ConflictType.DUPLICATE_DLC,
                    severity=ConflictSeverity.BLOCKING,
                    key=pack,
                    description=f"DLC pack '{pack}' is registered by: {', '.join(names)}",
                    owner=names[0],
                    owner_mod_ids=ids,
                    resolution_hint="Disable one of the conflicting mods",
                )
            )
        return tuple(conflicts)

    @staticmethod
    def _multiple_gameconfigs(installed: tuple[InstalledMod, ...]) -> tuple[Conflict, ...]:
        """Return a conflict when several mods ship a ``gameconfig.xml``."""
        owners = [
            (mod.mod_id, mod.display_name)
            for mod in installed
            if any(
                record.target_path.name.lower() == constants.GAMECONFIG_XML
                for record in mod.installed_files
            )
        ]
        if len(owners) < 2:
            return ()
        ids = tuple(mod_id for mod_id, _ in owners)
        names = tuple(name for _, name in owners)
        return (
            Conflict(
                conflict_type=ConflictType.DUPLICATE_GAMECONFIG,
                severity=ConflictSeverity.BLOCKING,
                key=constants.GAMECONFIG_XML,
                description=f"{len(owners)} mods install a custom gameconfig.xml: "
                + ", ".join(names),
                owner=names[0],
                owner_mod_ids=ids,
                resolution_hint="Keep exactly one gameconfig — disable the extras",
            ),
        )

    @staticmethod
    def _missing_files(installed: tuple[InstalledMod, ...]) -> tuple[Conflict, ...]:
        """Return a conflict per mod whose files disappeared from disk."""
        conflicts: list[Conflict] = []
        for mod in installed:
            missing = [
                record.target_path
                for record in mod.installed_files
                if not record.target_path.exists()
            ]
            if missing:
                conflicts.append(
                    Conflict(
                        conflict_type=ConflictType.MISSING_DEPENDENCY,
                        severity=ConflictSeverity.WARNING,
                        key=mod.display_name,
                        description=f"{mod.display_name} is missing {len(missing)} of its "
                        f"{mod.file_count} installed file(s)",
                        paths=tuple(missing[:10]),
                        owner=mod.display_name,
                        owner_mod_ids=(mod.mod_id,),
                        resolution_hint="Reinstall the mod, or disable / remove it",
                    )
                )
        return tuple(conflicts)
