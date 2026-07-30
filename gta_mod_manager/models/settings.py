"""User-configurable application settings."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path


@dataclass(frozen=True, slots=True)
class AppSettings:
    """Persisted user preferences.

    Attributes:
        game_root: Manually chosen or last used installation folder.
        auto_backup: Create a snapshot before every mutating operation.
        confirm_root_installs: Ask before writing outside the ``mods`` folder.
        keep_extracted_temp: Keep extraction workspaces for debugging.
        max_backup_generations: How many snapshots to keep per mod.
        theme: Name of the active GUI theme.
        language: UI language code (``en`` or ``vi``).
        crash_monitor_enabled: Watch the game process and report crashes.
        seven_zip_path: Optional external 7-Zip executable for exotic archives.
        unrar_path: Optional UnRAR/WinRAR executable used for ``.rar`` archives.
            Both tools are auto-detected, so this only matters for portable
            installations the detector cannot find.
        nexus_api_key: Personal Nexus Mods API key for online search / download.
    """

    game_root: Path | None = None
    auto_backup: bool = True
    confirm_root_installs: bool = True
    keep_extracted_temp: bool = False
    max_backup_generations: int = 3
    theme: str = "dark"
    language: str = "en"
    crash_monitor_enabled: bool = True
    seven_zip_path: Path | None = None
    unrar_path: Path | None = None
    nexus_api_key: str = ""
    recent_sources: tuple[Path, ...] = field(default_factory=tuple)

    def with_game_root(self, root: Path | None) -> AppSettings:
        """Return a copy of the settings pointing at another installation."""
        return replace(self, game_root=root)

    def with_recent_source(self, source: Path, limit: int = 10) -> AppSettings:
        """Return a copy with ``source`` pushed to the front of the MRU list."""
        remaining = [item for item in self.recent_sources if item != source]
        return replace(self, recent_sources=(source, *remaining)[:limit])
