"""Models for the bundled NCCVision graphics pack."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class GraphicsLevel(str, Enum):
    """Visual profile for NCCVision."""

    LIGHT = "light"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"
    DETAIL_AA = "detail_aa"
    CINEMATIC_DETAIL_AA = "cinematic_detail_aa"

    @property
    def display_name_key(self) -> str:
        """Return the i18n key for this level's label."""
        return f"graphics.level.{self.value}"

    @property
    def preset_filename(self) -> str:
        """Return the preset file name inside the pack."""
        return f"{self.value}.ini"


@dataclass(frozen=True, slots=True)
class GraphicsPackInfo:
    """Static description of a bundled graphics pack."""

    pack_id: str
    display_name: str
    description_key: str
    levels: tuple[GraphicsLevel, ...]


@dataclass(frozen=True, slots=True)
class GraphicsStatus:
    """Installed state of the graphics pack on a game root."""

    pack_id: str
    installed: bool
    level: GraphicsLevel | None
    injector_present: bool
    shaders_present: bool
    preset_path: Path | None
    conflict_enb: bool
    message: str = ""
    reshade_version: str | None = None
    reshade_latest: str | None = None
