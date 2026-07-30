"""JSON-backed storage of user preferences."""

from __future__ import annotations

from pathlib import Path

from gta_mod_manager.core.logging_setup import get_logger
from gta_mod_manager.models.settings import AppSettings
from gta_mod_manager.repository import codecs
from gta_mod_manager.repository.json_store import JsonStore

_LOGGER = get_logger("repository.settings")


class JsonSettingsRepository:
    """Loads and saves :class:`AppSettings`, caching the current value."""

    def __init__(self, store: JsonStore) -> None:
        self._store = store
        self._cached: AppSettings | None = None

    @classmethod
    def at(cls, path: Path) -> "JsonSettingsRepository":
        """Build a repository backed by the document at ``path``."""
        return cls(JsonStore(path, default={}))

    def load(self) -> AppSettings:
        """Return the stored settings, or defaults when none exist yet."""
        if self._cached is None:
            self._cached = codecs.decode_settings(self._store.read())
        return self._cached

    def save(self, settings: AppSettings) -> None:
        """Persist ``settings`` and update the cache."""
        self._store.write(codecs.encode_settings(settings))
        self._cached = settings
        _LOGGER.debug("Saved settings (game_root=%s)", settings.game_root)

    def reload(self) -> AppSettings:
        """Drop the cache and read the settings from disk again."""
        self._cached = None
        return self.load()
