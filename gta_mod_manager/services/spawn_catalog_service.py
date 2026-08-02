"""Catalog of spawn codes from installed vehicle and ped mods."""

from __future__ import annotations

from dataclasses import replace

from gta_mod_manager.installer.vehicle_keys import refine_vehicle_spawn_codes
from gta_mod_manager.models.enums import ModStatus
from gta_mod_manager.models.game_install import GameInstall
from gta_mod_manager.models.mod_package import InstalledMod
from gta_mod_manager.models.spawn import SpawnEntry, SpawnKind
from gta_mod_manager.plugins.gta_v.addon_peds import PED_META_MEMBER_PREFIX
from gta_mod_manager.services.library_service import LibraryService


class SpawnCatalogService:
    """Builds the Spawn Center list from the installed-mod library."""

    def __init__(self, library: LibraryService) -> None:
        self._library = library

    def list_entries(
        self,
        install: GameInstall | None = None,
        *,
        query: str = "",
        kind: SpawnKind | None = None,
    ) -> tuple[SpawnEntry, ...]:
        """Return spawnable codes for the active (or given) installation."""
        summaries = self._library.list_installed(install)
        entries: list[SpawnEntry] = []
        for summary in summaries:
            mod = summary.mod
            if mod.status is ModStatus.DISABLED:
                continue
            entries.extend(self._entries_for(mod))

        needle = query.strip().lower()
        filtered: list[SpawnEntry] = []
        for entry in entries:
            if kind is not None and entry.kind is not kind:
                continue
            if needle and needle not in entry.code.lower() and needle not in entry.mod_name.lower():
                continue
            filtered.append(entry)

        filtered.sort(key=self._newest_first)
        return tuple(filtered)

    @staticmethod
    def _newest_first(entry: SpawnEntry) -> tuple:
        """Sort key: newest install first, then spawn code A–Z."""
        stamp = entry.installed_at.timestamp() if entry.installed_at is not None else 0.0
        return (-stamp, entry.code.lower(), entry.mod_name.lower())

    def _entries_for(self, mod: InstalledMod) -> tuple[SpawnEntry, ...]:
        """Return every spawn code owned by ``mod``."""
        found: dict[tuple[str, SpawnKind], SpawnEntry] = {}
        ped_codes = self._ped_codes(mod)
        ped_keys = {code.lower() for code in ped_codes}
        is_ped_mod = self._is_ped_mod(mod) or bool(ped_keys)

        if not is_ped_mod:
            members = tuple(
                member
                for record in mod.installed_files
                for member in record.archive_members
            )
            for code in refine_vehicle_spawn_codes(mod.spawn_codes, members):
                cleaned = code.strip()
                if not cleaned or cleaned.lower() in ped_keys:
                    continue
                key = (cleaned.lower(), SpawnKind.VEHICLE)
                found[key] = SpawnEntry(
                    code=cleaned,
                    kind=SpawnKind.VEHICLE,
                    mod_id=mod.mod_id,
                    mod_name=mod.display_name,
                    tip="Type this in Menyoo / Simple Trainer to spawn the vehicle.",
                    mod_kind=mod.kind,
                    installed_at=mod.installed_at,
                )

        # Ped packs often also stash model names in ``spawn_codes``; treat those
        # as ped names when the mod is a character pack (or has pedmeta members).
        ped_names = list(ped_codes)
        if is_ped_mod:
            for code in mod.spawn_codes:
                cleaned = code.strip()
                if cleaned and cleaned.lower() not in ped_keys:
                    ped_names.append(cleaned)
                    ped_keys.add(cleaned.lower())

        for code in ped_names:
            key = (code.lower(), SpawnKind.PED)
            found[key] = SpawnEntry(
                code=code,
                kind=SpawnKind.PED,
                mod_id=mod.mod_id,
                mod_name=mod.display_name,
                tip="Change player model / ped spawn with this name in Menyoo or PedSelector.",
                mod_kind=mod.kind or "ped",
                installed_at=mod.installed_at,
            )
        return tuple(found.values())

    @staticmethod
    def _is_ped_mod(mod: InstalledMod) -> bool:
        """Return whether ``mod`` is classified as a ped / character pack."""
        kind = mod.kind.strip().lower()
        return kind in {"ped", "peds", "addon_ped", "character"} or "ped" in kind

    @staticmethod
    def sanitized_vehicle_codes(mod: InstalledMod) -> tuple[str, ...]:
        """Return vehicle spawn codes only (empty for ped packs)."""
        if SpawnCatalogService._is_ped_mod(mod):
            return ()
        members = tuple(
            member
            for record in mod.installed_files
            for member in record.archive_members
        )
        ped_keys = {
            member[len(PED_META_MEMBER_PREFIX) :].strip().lower()
            for record in mod.installed_files
            for member in record.archive_members
            if member.startswith(PED_META_MEMBER_PREFIX)
        }
        return tuple(
            code
            for code in refine_vehicle_spawn_codes(mod.spawn_codes, members)
            if code.lower() not in ped_keys
        )

    @classmethod
    def with_sanitized_spawn_codes(cls, mod: InstalledMod) -> InstalledMod:
        """Return ``mod`` with vehicle spawn codes cleaned for display / storage."""
        cleaned = cls.sanitized_vehicle_codes(mod)
        current = tuple(code.strip() for code in mod.spawn_codes if code.strip())
        if cleaned == current:
            return mod
        return replace(mod, spawn_codes=cleaned)

    @staticmethod
    def _ped_codes(mod: InstalledMod) -> tuple[str, ...]:
        """Extract ped model stems from manager-owned archive members."""
        codes: list[str] = []
        seen: set[str] = set()
        for record in mod.installed_files:
            for member in record.archive_members:
                if not member.startswith(PED_META_MEMBER_PREFIX):
                    continue
                stem = member[len(PED_META_MEMBER_PREFIX) :].strip().lower()
                if not stem or stem in seen:
                    continue
                seen.add(stem)
                codes.append(stem)
        return tuple(codes)
