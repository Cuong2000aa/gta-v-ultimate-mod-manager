"""Model for conflicts detected before an installation is applied."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from gta_mod_manager.models.enums import ConflictSeverity, ConflictType


@dataclass(frozen=True, slots=True)
class Conflict:
    """A single problem found between a plan and the current game state.

    Attributes:
        conflict_type: Category of the conflict.
        severity: Whether the conflict merely warns or blocks the install.
        key: The colliding identifier (spawn code, DLC name, file name...).
        description: Human readable explanation.
        paths: Files involved in the conflict.
        owner: Mod that currently owns the colliding resource, when known.
        owner_mod_ids: Library ids for mods involved (for one-click disable).
        resolution_hint: Suggested action shown in the conflict center.
    """

    conflict_type: ConflictType
    severity: ConflictSeverity
    key: str
    description: str
    paths: tuple[Path, ...] = field(default_factory=tuple)
    owner: str | None = None
    owner_mod_ids: tuple[str, ...] = ()
    resolution_hint: str | None = None

    @property
    def is_blocking(self) -> bool:
        """Return whether this conflict prevents installation."""
        return self.severity.is_blocking


@dataclass(frozen=True, slots=True)
class ConflictReport:
    """Aggregated conflicts for one install plan."""

    conflicts: tuple[Conflict, ...] = field(default_factory=tuple)

    @property
    def is_empty(self) -> bool:
        """Return whether nothing was detected."""
        return not self.conflicts

    @property
    def blocking(self) -> tuple[Conflict, ...]:
        """Return only the conflicts that block installation."""
        return tuple(item for item in self.conflicts if item.is_blocking)

    @property
    def warnings(self) -> tuple[Conflict, ...]:
        """Return only the conflicts of severity ``WARNING``."""
        return tuple(
            item for item in self.conflicts if item.severity is ConflictSeverity.WARNING
        )

    @property
    def has_blocking(self) -> bool:
        """Return whether at least one blocking conflict exists."""
        return bool(self.blocking)

    def by_type(self, conflict_type: ConflictType) -> tuple[Conflict, ...]:
        """Return every conflict of the requested type."""
        return tuple(item for item in self.conflicts if item.conflict_type is conflict_type)

    def grouped(self) -> dict[ConflictType, tuple[Conflict, ...]]:
        """Return the conflicts grouped by type, for the conflict center."""
        groups: dict[ConflictType, list[Conflict]] = {}
        for item in self.conflicts:
            groups.setdefault(item.conflict_type, []).append(item)
        return {key: tuple(value) for key, value in groups.items()}

    def merged_with(self, other: "ConflictReport") -> "ConflictReport":
        """Return a report containing the conflicts of both reports."""
        return ConflictReport(conflicts=(*self.conflicts, *other.conflicts))
