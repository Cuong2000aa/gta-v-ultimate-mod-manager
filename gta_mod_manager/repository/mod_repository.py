"""JSON-backed repository of installed mods."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from gta_mod_manager.core.logging_setup import get_logger
from gta_mod_manager.models.enums import ModStatus
from gta_mod_manager.models.mod_package import InstalledMod
from gta_mod_manager.repository import codecs
from gta_mod_manager.repository.json_store import JsonStore
from gta_mod_manager.utils import fs

_LOGGER = get_logger("repository.mods")

_SCHEMA_VERSION = 1


class JsonModRepository:
    """Stores the installed-mod records in a single JSON document."""

    def __init__(self, store: JsonStore) -> None:
        self._store = store

    @classmethod
    def at(cls, path: Path) -> "JsonModRepository":
        """Build a repository backed by the document at ``path``."""
        return cls(JsonStore(path, default={"version": _SCHEMA_VERSION, "mods": {}}))

    def add(self, mod: InstalledMod) -> None:
        """Insert ``mod``, replacing any record with the same identifier."""

        def mutate(payload: dict[str, Any]) -> dict[str, Any]:
            mods = dict(payload.get("mods", {}))
            mods[mod.mod_id] = codecs.encode_installed_mod(mod)
            return {"version": _SCHEMA_VERSION, "mods": mods}

        self._store.update(mutate)
        _LOGGER.info("Registered installed mod %s (%s)", mod.display_name, mod.mod_id)

    def remove(self, mod_id: str) -> None:
        """Delete the record identified by ``mod_id`` if it exists."""

        def mutate(payload: dict[str, Any]) -> dict[str, Any]:
            mods = dict(payload.get("mods", {}))
            mods.pop(mod_id, None)
            return {"version": _SCHEMA_VERSION, "mods": mods}

        self._store.update(mutate)
        _LOGGER.info("Removed installed mod record %s", mod_id)

    def get(self, mod_id: str) -> InstalledMod | None:
        """Return the record identified by ``mod_id``, or ``None``."""
        payload = self._store.read().get("mods", {}).get(mod_id)
        return codecs.decode_installed_mod(payload) if payload else None

    def list_all(self) -> tuple[InstalledMod, ...]:
        """Return every tracked mod, newest installation first."""
        records = [
            codecs.decode_installed_mod(item)
            for item in self._store.read().get("mods", {}).values()
        ]
        records.sort(key=lambda item: item.installed_at, reverse=True)
        return tuple(records)

    def list_for_game(self, game_root: Path) -> tuple[InstalledMod, ...]:
        """Return the mods installed into ``game_root``."""
        return tuple(
            record
            for record in self.list_all()
            if fs.normalise(record.game_root) == fs.normalise(game_root)
        )

    def list_active(self) -> tuple[InstalledMod, ...]:
        """Return the mods that are currently enabled."""
        return tuple(
            record for record in self.list_all() if record.status is ModStatus.INSTALLED
        )

    def find_owner_of(self, target_path: Path) -> InstalledMod | None:
        """Return the mod that installed ``target_path``, when tracked.

        Used by the conflict detector to name the mod a new package would
        overwrite.
        """
        needle = fs.normalise(target_path)
        for record in self.list_all():
            for file in record.installed_files:
                if fs.normalise(file.target_path) == needle:
                    return record
        return None

    def update_status(self, mod_id: str, status: ModStatus) -> InstalledMod | None:
        """Change the status of ``mod_id`` and return the updated record."""
        existing = self.get(mod_id)
        if existing is None:
            return None
        updated = existing.with_status(status)
        self.add(updated)
        return updated
