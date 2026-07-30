"""Catalog of spawn codes from installed vehicle and ped mods."""

from __future__ import annotations

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

        filtered.sort(key=lambda item: (item.kind.value, item.code.lower(), item.mod_name.lower()))
        return tuple(filtered)

    def _entries_for(self, mod: InstalledMod) -> tuple[SpawnEntry, ...]:
        """Return every spawn code owned by ``mod``."""
        found: dict[tuple[str, SpawnKind], SpawnEntry] = {}
        for code in mod.spawn_codes:
            cleaned = code.strip()
            if not cleaned:
                continue
            key = (cleaned.lower(), SpawnKind.VEHICLE)
            found[key] = SpawnEntry(
                code=cleaned,
                kind=SpawnKind.VEHICLE,
                mod_id=mod.mod_id,
                mod_name=mod.display_name,
                tip="Type this in Menyoo / Simple Trainer to spawn the vehicle.",
            )
        for code in self._ped_codes(mod):
            key = (code.lower(), SpawnKind.PED)
            found[key] = SpawnEntry(
                code=code,
                kind=SpawnKind.PED,
                mod_id=mod.mod_id,
                mod_name=mod.display_name,
                tip="Change player model / ped spawn with this name in Menyoo or PedSelector.",
            )
        # Ped packages sometimes store the model only as the kind label.
        if mod.kind.lower() == "ped" and not any(
            entry.kind is SpawnKind.PED for entry in found.values()
        ):
            # Fall back: nothing recorded — still useful to show the mod name tip.
            pass
        return tuple(found.values())

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
