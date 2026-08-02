"""Models for the Spawn Center catalog."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class SpawnKind(str, Enum):
    """What kind of in-game asset a spawn code refers to."""

    VEHICLE = "vehicle"
    PED = "ped"

    @property
    def display_name(self) -> str:
        """Return a short English label."""
        return "Vehicle" if self is SpawnKind.VEHICLE else "Ped / character"


@dataclass(frozen=True, slots=True)
class SpawnEntry:
    """One spawnable code owned by an installed mod."""

    code: str
    kind: SpawnKind
    mod_id: str
    mod_name: str
    tip: str = ""
    #: Analyzer / library category (e.g. ``vehicle_addon``, ``vehicle_replace``).
    mod_kind: str = ""
    #: When the owning mod was installed — used to list newest mods first.
    installed_at: datetime | None = None
