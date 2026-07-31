"""Models for the Essentials Kit installer."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class EssentialAction(str, Enum):
    """How the kit can satisfy one essential component."""

    INSTALLED = "installed"
    AUTO_INSTALL = "auto_install"
    OPEN_BROWSER = "open_browser"
    CREATE_FOLDER = "create_folder"


@dataclass(frozen=True, slots=True)
class EssentialItem:
    """One component tracked by the essentials kit."""

    component_id: str
    display_name: str
    installed: bool
    action: EssentialAction
    detail: str = ""
    homepage: str = ""


@dataclass(frozen=True, slots=True)
class EssentialsStatus:
    """Overall readiness of the Story Mode essentials stack."""

    items: tuple[EssentialItem, ...]
    ready: bool
    message: str
    auto_installable: tuple[str, ...]
    browser_needed: tuple[str, ...]

    @property
    def missing_count(self) -> int:
        """How many essentials are still missing."""
        return sum(1 for item in self.items if not item.installed)
