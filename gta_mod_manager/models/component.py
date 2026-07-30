"""Model for third-party components such as ScriptHookV or ReShade."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from gta_mod_manager.models.enums import ComponentStatus


@dataclass(frozen=True, slots=True)
class ComponentSpec:
    """Static description of a component the detector can look for.

    Attributes:
        component_id: Stable identifier, see ``core.constants``.
        display_name: Label shown in the dashboard.
        required_by: Categories of mods that depend on this component.
        homepage: Where the user can obtain the component.
        is_essential: Whether most mod setups break without it.
    """

    component_id: str
    display_name: str
    required_by: tuple[str, ...] = field(default_factory=tuple)
    homepage: str | None = None
    is_essential: bool = False


@dataclass(frozen=True, slots=True)
class DetectedComponent:
    """Runtime state of a component inside a concrete game installation."""

    spec: ComponentSpec
    status: ComponentStatus
    version: str | None = None
    location: Path | None = None
    details: str | None = None

    @property
    def component_id(self) -> str:
        """Return the identifier of the underlying specification."""
        return self.spec.component_id

    @property
    def display_name(self) -> str:
        """Return the label of the underlying specification."""
        return self.spec.display_name

    @property
    def is_installed(self) -> bool:
        """Return whether the component was found on disk."""
        return self.status is ComponentStatus.INSTALLED

    @property
    def is_missing_dependency(self) -> bool:
        """Return whether an essential component is absent."""
        return self.spec.is_essential and not self.is_installed


@dataclass(frozen=True, slots=True)
class ComponentReport:
    """Result of a full component scan of one installation."""

    components: tuple[DetectedComponent, ...] = field(default_factory=tuple)

    @property
    def installed(self) -> tuple[DetectedComponent, ...]:
        """Return only the components that are present."""
        return tuple(item for item in self.components if item.is_installed)

    @property
    def missing_dependencies(self) -> tuple[DetectedComponent, ...]:
        """Return essential components that are not installed."""
        return tuple(item for item in self.components if item.is_missing_dependency)

    def find(self, component_id: str) -> DetectedComponent | None:
        """Return the entry for ``component_id`` when it was scanned."""
        for item in self.components:
            if item.component_id == component_id:
                return item
        return None

    def has(self, component_id: str) -> bool:
        """Return whether ``component_id`` is installed."""
        entry = self.find(component_id)
        return entry is not None and entry.is_installed
